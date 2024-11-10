from datetime import datetime, timezone

from praw import Reddit
from praw.reddit import Submission as PRAWSubmission

from django.conf import settings
from django.db import transaction

from core.use_cases import UseCase
from collector.models import (
    Comment,
    Redditor,
    Submission,
    Subreddit,
)

class CollectThreadsUseCase(UseCase):
    """
    Use case that collects all threads for configured subreddits and stores/updates them in the database.
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
            author_flair_text=submission.author_flair_text,
            link_flair_text=submission.link_flair_text,
            link_flair_template_id=submission.link_flair_template_id,
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
        instance.author_flair_text = submission.author_flair_text
        instance.link_flair_text = submission.link_flair_text
        instance.link_flair_template_id = submission.link_flair_template_id
        
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
            distinguished=comment.distinguished is not None,
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
        instance.distinguished = comment.distinguished is not None
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