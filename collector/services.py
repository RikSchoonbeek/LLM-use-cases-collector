from datetime import datetime, timezone
from typing import Dict, List, Any, Type

from openai import OpenAI
from praw import Reddit
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

class CollectThreadsService(Service):
    """
    Service that collects all threads for configured subreddits and stores/updates them in the database.
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
            
            # Atomic transaction per submission guarantees complete submission information storage
            with transaction.atomic():
                submission_instance = self.process_submission(submission, subreddit_instance)
                self.process_submission_comments(submission, submission_instance)
                self.log_info(f"  Finished processing Submission\n")

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
    def execute(self, input_text: str):
        # Goal: I want to know which submission (and comments) are judged to contain specific info
        # Maybe I can create a Model class that represents a check for specific information in a
        # source.
        # This model could contain instructions that can be converted into a pydantic BaseModel
        # to be used for a question like the one below.
        # The model can also contain a foreignkey to a submission, if the submission was judged
        # to contain the information specified in the Model
        # TODO steps:
        # 1 

        # x I 

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        for info_to_detect in InformationToDetect.objects.all():
            messages = self.get_initial_llm_messages(info_to_detect, input_text)
            response_format = self.create_pydantic_model(format_instance=info_to_detect.response_format)
            completion = client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=messages,
                response_format=response_format,
            )
            
            # Access the parsed response
            result = completion.choices[0].message.parsed
            return {
                "contains_llm_use_case_info": result.contains_llm_use_case_info,
                "explanation": result.explanation
            }
        
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
            field.name: self.get_python_type(field.data_type) for field in fields
        }
        
        model = create_model(
            format_instance.name,
            **field_definitions,
            __base__=BaseModel
        )
        
        return model

    
    def get_initial_llm_messages(self, info_to_detect: InformationToDetect, input_text) -> List[Dict]:
        """
        example response:
        messages=[
                {
                    "role": "system",
                    "content": "Analyze the provided text to determine if it contains information about LLM use cases. Provide a brief explanation of what you found or why no use cases were present."
                },
                {
                    "role": "user",
                    "content": input_text
                }
            ]
        """
        return [
            {
                "role": "system",
                "content": info_to_detect.llm_instruction_message,
            },
            {
                "role": "user",
                "content": input_text
            }
        ]