from datetime import datetime, timezone
import time
from typing import Dict, List, Any, Type

import anthropic
from praw import Reddit
import prawcore
from praw.reddit import Submission as PRAWSubmission
from pydantic import BaseModel, create_model

from django.conf import settings
from django.db import transaction

from core.services import Service
from collector.models import (
    Comment,
    InformationToDetect,
    Redditor,
    Submission,
    Subreddit,
    PydanticResponseFormat,
    PydanticResponseFormatField,
)

class CollectSubmissionsService(Service):
    """
    Service that collects all submissions for configured subreddits and stores/updates them in the database.
    """

    def execute(self):
        self.reddit_interface = Reddit(
            client_id=settings.REDDIT_API_CLIENT_ID,
            client_secret=settings.REDDIT_API_CLIENT_SECRET,
            password=settings.REDDIT_ACCOUNT_PASSWORD,
            user_agent="LLM_use_case_tracker/1.0",
            username=settings.REDDIT_ACCOUNT_USERNAME,
        )
        
        for subreddit in Subreddit.objects.all():
            self.log_info(f"Processing Subreddit: {subreddit.name}\n")
            self.process_subreddit(subreddit_instance=subreddit)
    
    def process_subreddit(self, subreddit_instance: Subreddit):
        # Map to store all comment data by id: instance. Acting as a temporary cache to prevent database calls.
        self.submission_comments = {}
        subreddit = self.reddit_interface.subreddit(subreddit_instance.name)
        for submission in subreddit.new():
            self.log_info(f"  Processing Submission: {submission.title}")

            try:
                # Atomic transaction per submission guarantees complete submission information storage
                with transaction.atomic():
                    submission_instance = self.process_submission(submission, subreddit_instance)
                    self.process_submission_comments(submission, submission_instance)
                    self.log_info(f"  Finished processing Submission\n")
            except prawcore.exceptions.TooManyRequests as e:
                error_raised = True

            
            # Each submission gets 5 attempts. prawcore.exceptions.TooManyRequests Exceptions sometimes
            # happen, and this mechanic helps give each submission 5 attempts, retrying after
            error_raised = False
            retry_attempts = 5
            while True:
                try:
                    # Atomic transaction per submission guarantees complete submission information storage
                    with transaction.atomic():
                        submission_instance = self.process_submission(submission, subreddit_instance)
                        self.process_submission_comments(submission, submission_instance)
                        self.log_info(f"  Finished processing Submission\n")
                        break
                        # If no error occured, this loop is done. The rest is only a retry mechanism for errors.
                except prawcore.exceptions.TooManyRequests as e:
                    self.log_info("  prawcore.exceptions.TooManyRequests raised during self.process_submission_comments(...) execution\n")
                    
                    # If error wasn't previously raised the retries are initiated. Each retry is detracted after
                    # that and the exception is re-raised when retries are gone.
                    if not error_raised:
                        retry_attempts = 5
                    elif retry_attempts == 0:
                        raise e
                        # This will also break the while loop
                    else:
                        retry_attempts -= 1
                    
                    self.log_info(f"   Waiting 15 seconds before next retry - retries left: {attempts}")
                    time.sleep(15)
                    self.log_info("   Retry started")

    def process_submission(self, submission: PRAWSubmission, subreddit_instance: Subreddit) -> Submission:
        """Process a submission, creating or updating it as needed."""
        try:
            submission_instance = Submission.objects.get(reddit_id=submission.id)
            # Check if submission needs updating
            submission_edited_dt_utc = datetime.fromtimestamp(submission.edited, timezone.utc) if submission.edited else None
            
            # Update if either:
            # 1. The submission has been edited and our stored version is older
            # 2. The submission has never been edited but other fields might have changed (score, comments, etc.)
            if (submission_edited_dt_utc and 
                (not submission_instance.edited_utc or submission_edited_dt_utc > submission_instance.edited_utc)):
                self.log_info("  Updating existing submission due to new edits")
                self._update_submission(submission_instance, submission)
            else:
                self.log_info("  Updating existing submission metadata")
                self._update_submission_metadata(submission_instance, submission)
                
        except Submission.DoesNotExist:
            self.log_info("  Creating new submission")
            submission_instance = self._create_submission(submission, subreddit_instance)

        return submission_instance

    def _create_submission(self, submission: PRAWSubmission, subreddit_instance: Subreddit) -> Submission:
        """Create a new submission instance."""
        author_instance = self._get_or_create_author(submission.author)
        edited_dt_utc = datetime.fromtimestamp(submission.edited, timezone.utc) if submission.edited else None
        submission_created_dt_utc = datetime.fromtimestamp(submission.created_utc, timezone.utc)
        
        return Submission.objects.create(
            reddit_id=submission.id,
            author=author_instance,
            subreddit=subreddit_instance,
            title=submission.title,
            selftext=submission.selftext,
            url=submission.url,
            created_utc=submission_created_dt_utc,
            score=submission.score,
            upvote_ratio=submission.upvote_ratio,
            num_comments=submission.num_comments,
            over_18=submission.over_18,
            spoiler=submission.spoiler,
            stickied=submission.stickied,
            distinguished=submission.distinguished,
            edited_utc=edited_dt_utc,
            locked=submission.locked,
            saved=submission.saved,
            is_original_content=submission.is_original_content,
            is_self=submission.is_self,
            permalink=submission.permalink,
            author_flair_text=getattr(submission, "author_flair_text", None),
            link_flair_text=getattr(submission, "link_flair_text", None),
            link_flair_template_id=getattr(submission, "link_flair_template_id", None),
        )

    def _update_submission(self, instance: Submission, submission: PRAWSubmission) -> None:
        """Update all fields of an existing submission."""
        author_instance = self._get_or_create_author(submission.author)
        edited_dt_utc = datetime.fromtimestamp(submission.edited, timezone.utc) if submission.edited else None
        
        # Update all fields that might have changed
        instance.author = author_instance
        instance.title = submission.title
        instance.selftext = submission.selftext
        instance.url = submission.url
        instance.score = submission.score
        instance.upvote_ratio = submission.upvote_ratio
        instance.num_comments = submission.num_comments
        instance.over_18 = submission.over_18
        instance.spoiler = submission.spoiler
        instance.stickied = submission.stickied
        instance.distinguished = submission.distinguished
        instance.edited_utc = edited_dt_utc
        instance.locked = submission.locked
        instance.saved = submission.saved
        instance.is_original_content = submission.is_original_content
        instance.is_self = submission.is_self
        instance.permalink = submission.permalink
        instance.author_flair_text = getattr(submission, "author_flair_text", None)
        instance.link_flair_text = getattr(submission, "link_flair_text", None)
        instance.link_flair_template_id = getattr(submission, "link_flair_template_id", None)
        
        instance.save()

    def _update_submission_metadata(self, instance: Submission, submission: PRAWSubmission) -> None:
        """Update only the metadata fields that commonly change."""
        instance.score = submission.score
        instance.upvote_ratio = submission.upvote_ratio
        instance.num_comments = submission.num_comments
        instance.stickied = submission.stickied
        instance.locked = submission.locked
        instance.saved = submission.saved
        
        instance.save()

    def process_submission_comments(self, submission: PRAWSubmission, submission_instance: Submission):
        # Get all comments
        submission.comments.replace_more(limit=None)  # Expand all comment trees
        
        # Load existing comments for this submission into our cache
        existing_comments = Comment.objects.filter(submission=submission_instance)
        self.submission_comments = {comment.reddit_id: comment for comment in existing_comments}
        
        for comment in submission.comments.list():
            self.log_info(f"    Processing Comment with reddit id: {comment.id}")
            
            try:
                comment_instance = self.submission_comments[comment.id]
                comment_edited_dt_utc = datetime.fromtimestamp(comment.edited, timezone.utc) if comment.edited else None
                
                # Update if the comment has been edited and our stored version is older
                if comment_edited_dt_utc and (not comment_instance.edited_utc or comment_edited_dt_utc > comment_instance.edited_utc):
                    self.log_info("    Updating existing comment due to new edits")
                    self._update_comment(comment_instance, comment, submission_instance)
                else:
                    self.log_info("    Updating existing comment metadata")
                    self._update_comment_metadata(comment_instance, comment)
                    
            except KeyError:
                self.log_info("    Creating new comment")
                comment_instance = self._create_comment(comment, submission_instance)
                self.submission_comments[comment.id] = comment_instance

    def _create_comment(self, comment, submission_instance: Submission) -> Comment:
        """Create a new comment instance."""
        author_instance = self._get_or_create_author(comment.author)
        parent_comment = self.submission_comments.get(self.format_id(comment.parent_id))
        
        edited_dt_utc = datetime.fromtimestamp(comment.edited, timezone.utc) if comment.edited else None
        comment_created_dt_utc = datetime.fromtimestamp(comment.created_utc, timezone.utc)
        
        return Comment.objects.create(
            reddit_id=comment.id,
            submission=submission_instance,
            author=author_instance,
            body=comment.body,
            body_html=comment.body_html,
            created_utc=comment_created_dt_utc,
            score=comment.score,
            parent=parent_comment,
            distinguished=comment.distinguished,
            edited_utc=edited_dt_utc,
            stickied=comment.stickied,
            saved=comment.saved,
            is_submitter=comment.is_submitter,
            permalink=comment.permalink,
        )

    def _update_comment(self, instance: Comment, comment, submission_instance: Submission) -> None:
        """Update all fields of an existing comment."""
        author_instance = self._get_or_create_author(comment.author)
        parent_comment = self.submission_comments.get(self.format_id(comment.parent_id))
        edited_dt_utc = datetime.fromtimestamp(comment.edited, timezone.utc) if comment.edited else None
        
        instance.author = author_instance
        instance.body = comment.body
        instance.body_html = comment.body_html
        instance.score = comment.score
        instance.parent = parent_comment
        instance.distinguished = comment.distinguished
        instance.edited_utc = edited_dt_utc
        instance.stickied = comment.stickied
        instance.saved = comment.saved
        instance.is_submitter = comment.is_submitter
        instance.permalink = comment.permalink
        
        instance.save()

    def _update_comment_metadata(self, instance: Comment, comment) -> None:
        """Update only the metadata fields that commonly change."""
        instance.score = comment.score
        instance.stickied = comment.stickied
        instance.saved = comment.saved
        
        instance.save()

    def _get_or_create_author(self, author) -> Redditor:
        """Get or create a Redditor instance for the given author."""
        if not author:
            return None
            
        author_created_dt_utc = None
        if getattr(author, "created_utc", None):
            author_created_dt_utc = datetime.fromtimestamp(author.created_utc, timezone.utc)
        
        author_instance, _ = Redditor.objects.get_or_create(
            username=author.name,
            created_utc=author_created_dt_utc,
        )
        return author_instance

    @staticmethod
    def format_id(id_str, id_type=None):
        """
        [Documentation remains the same as in original code]
        """
        prefix_map = {
            'Submission': 't3',
            'Comment': 't1',
            'User': 't2',
            'Message': 't4',
            'Subreddit': 't5',
            'Award': 't6'
        }
        
        if id_type:
            prefix = prefix_map.get(id_type)
            if not prefix:
                raise ValueError('Invalid id_type provided.')
            return f'{prefix}_{id_str}'
        
        return id_str[3:]

    def log_info(self, message: str):
        print(message)


class UseCaseAnalysis(BaseModel):
    contains_llm_use_case_info: bool
    explanation: str


class CheckSubmissionForInformationService(Service):
    def execute(self, submissions: List[Submission] = None):
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        found_count = 0
        total_processed = 0

        for info_to_detect in InformationToDetect.objects.all():
            for submission in submissions:
                print(f"processing submission with id: {submission.id}")
                submission_text = self.get_submission_text(submission)
                response_format = self.create_pydantic_model(format_instance=info_to_detect.response_format)
                text_analysis_schema = response_format.model_json_schema()
    
                tools = [
                    {
                        "name": "build_text_analysis_result",
                        "description": "build the text analysis object",
                        "input_schema": text_analysis_schema
                    }
                ]

                message = client.messages.create(
                    system=info_to_detect.llm_instruction_message,
                    messages=[
                        {
                            "role": "user",
                            "content": submission_text,
                        }
                    ],
                    model="claude-3-haiku-20240307",
                    # max_tokens: (1200) Maximum length of model's response. Higher values allow for longer, more detailed responses.
                    max_tokens=1200,
                    # temperature: (0.2) Controls response randomness/creativity. 0.2 is good for accurate, predictable outputs.
                    temperature=0.2,
                    tools=tools,
                    tool_choice={"type": "tool", "name": "build_text_analysis_result"}
                )

                function_call = message.content[0].input
                formatted_response =  response_format(**function_call)
                total_processed += 1

                if formatted_response.contains_relevant_examples:
                    found_count += 1
                
                len([])


    def get_submission_text(self, submission: Submission) -> str:
        """
        Format a Reddit submission and its comments into a readable text conversation.
        
        Args:
            submission: A Submission instance with prefetched comments
            
        Returns:
            str: Formatted text representation of the thread
        """
        # Initialize output with submission details
        output = [
            f"Title: {submission.title}\n",
            f"Posted by u/{submission.author.username if submission.author else '[deleted]'}\n"
        ]
        
        # Add submission text if it exists
        if submission.selftext.strip():
            output.append(f"\n{submission.selftext}\n")
        
        output.append("\n" + "-"*50 + "\nComments:\n")
        
        def format_comment(comment, depth=0):
            """Helper function to recursively format comments with proper indentation"""
            indent = "    " * depth
            author = comment.author.username if comment.author else '[deleted]'
            
            # Format the comment with indentation
            comment_text = f"{indent}u/{author}:\n{indent}{comment.body}\n"
            
            # Recursively format child comments
            for child in comment.get_children():
                comment_text += "\n" + format_comment(child, depth + 1)
                
            return comment_text
        
        # Get all root comments (comments without parents)
        root_comments = submission.comments.filter(parent=None).order_by('created_utc')
        
        # Format each comment tree
        for comment in root_comments:
            output.append(format_comment(comment))
            output.append("\n")
        
        return "".join(output)


        
    def get_python_type(self, data_type: str) -> Type:
        type_mapping = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'dict': Dict[str, Any],
            'list': list,
            'tuple': tuple,
            'set': set,
            'none': None
        }
        return type_mapping.get(data_type, str)

    def create_pydantic_model(self, format_instance: PydanticResponseFormat) -> Type[BaseModel]:
        fields = PydanticResponseFormatField.objects.filter(base_model=format_instance)
        
        field_definitions = {
            field.name: (self.get_python_type(field.data_type), ...) 
            for field in fields
        }
        
        model = create_model(
            format_instance.name,
            **field_definitions,
            __base__=BaseModel
        )
        
        return model
    