from datetime import datetime, timezone

from praw import Reddit
from praw.reddit import Submission as PRAWSubmission

from django.conf import settings
from django.db import transaction

from core.services import UseCase
from collector.models import (
    Comment,
    Redditor,
    Submission,
    Subreddit,
)

class CollectThreadsUseCase(UseCase):
    """
    Use case that collects all threads for configured subreddits and stores them in the database.
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
        # Map to store all comment data by id: instance. Acting as a temporary cash to prevent database calls.
        self.submission_comments = {}
        subreddit = self.reddit_interface.subreddit(subreddit_instance.name)
        for submission in subreddit.new():
            self.log_info(f"  Processing Submission: {submission.title}")
            # Atomic transaction per submission guarantees complete submission information storage
            # TODO will need to update this code so that submissions are updated instead of only created once
            with transaction.atomic():
                try:
                    Submission.objects.get(reddit_id=submission.id)
                except Submission.DoesNotExist:
                    pass
                else:
                    print(f"  Submission found that was already stored. It is skipped.\nIn the future I want to update existing Submissions instead of skipping them.")
                    continue
                
                author_created_dt_utc = None
                author_instance = None
                if submission.author:
                    if hasattr(submission.author, "created_utc") and submission.author.created_utc:
                        author_created_dt_utc = datetime.fromtimestamp(submission.author.created_utc, timezone.utc)
                    
                    author_instance, created = Redditor.objects.get_or_create(
                        username=submission.author.name,
                        created_utc=author_created_dt_utc,
                    )
                
                edited_dt_utc = None
                if submission.edited:
                    edited_dt_utc = datetime.fromtimestamp(submission.edited, timezone.utc)
                submission_created_dt_utc = datetime.fromtimestamp(submission.created_utc, timezone.utc)
                submission_instance = Submission.objects.create(
                    reddit_id=submission.id,
                    author=author_instance,
                    subreddit=subreddit_instance,
                    title=submission.title,
                    selftext=submission.selftext ,
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

                self.process_submission_comments(submission, submission_instance)

                self.log_info(f"  Finished rocessing Submission\n")

    def process_submission_comments(self, submission: PRAWSubmission, submission_instance: Submission):
        # Get all comments
            submission.comments.replace_more(limit=None)  # Expand all comment trees

            # Using `submission.comments.list()` after `submission.comments.replace_more(limit=None)`
            # seems to give access to the whole comment tree of a submission.
            # TODO may need to make sure this is the case
            for comment in submission.comments.list():
                self.log_info(f"    Processing Comment with reddit id: {comment.id}")
                author_created_dt_utc = None
                author_instance = None
                if comment.author:
                    if hasattr(comment.author, "created_utc") and comment.author.created_utc:
                        author_created_dt_utc = datetime.fromtimestamp(comment.author.created_utc, timezone.utc)
                    
                    author_instance, created = Redditor.objects.get_or_create(
                        username=comment.author.name,
                        created_utc=author_created_dt_utc,
                    )

                parent_comment = self.submission_comments.get(self.format_id(comment.parent_id))
                # t3 seems to be the indicator of a submission (or link or post)
                comment_is_direct_submission_child = comment.parent_id == self.format_id(submission.id, "Submission")
                if not comment_is_direct_submission_child and not parent_comment:
                    raise Exception(
                        "Tried to persist child Comment for Submission without it's parent Comment being created first."
                        "If this occurs this means that the order in which submission.comments is returned is not"
                        "from higest level (parents) to lowest (children), and a solution could be to first store"
                        "all comment data in memory before persisting it to the database."
                    )
                
                edited_dt_utc = None
                if comment.edited:
                    edited_dt_utc = datetime.fromtimestamp(comment.edited, timezone.utc)
                commment_created_dt_utc = datetime.fromtimestamp(comment.created_utc, timezone.utc)
                commment_instance = Comment.objects.create(
                    reddit_id=comment.id,
                    submission=submission_instance,
                    author=author_instance,
                    body=comment.body,
                    body_html=comment.body_html,
                    created_utc=commment_created_dt_utc,
                    score=comment.score,
                    parent=parent_comment,
                    distinguished=comment.distinguished is not None,
                    edited_utc=edited_dt_utc,
                    stickied=comment.stickied,
                    saved=comment.saved,
                    is_submitter=comment.is_submitter,
                    permalink=comment.permalink,
                )
                self.submission_comments[comment.id] = commment_instance

    @staticmethod
    def format_id(id_str, id_type=None):
        """
        Formats or strips the given ID based on the provided direction and content type.

        - If `id_type` is provided, the function formats the ID by adding the appropriate prefix for the specified content type.
        - If `id_type` is None, the function assumes the input is already a formatted ID and strips the prefix.

        Parameters:
        - id_str (str): The ID, which may be with or without a prefix.
        - id_type (str or None): If specified, adds a prefix for the given content type. Allowed values are:
            - 'Submission' for submissions (t3)
            - 'Comment' for comments (t1)
            - 'User' for user accounts (t2)
            - 'Message' for private messages (t4)
            - 'Subreddit' for subreddits (t5)
            - 'Award' for awards (t6)
          If `id_type` is None, the function assumes `id_str` already includes a prefix.

        Returns:
        - str: The formatted or stripped ID.
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
            # Add prefix based on id_type
            prefix = prefix_map.get(id_type)
            if not prefix:
                raise ValueError('Invalid id_type provided.')
            return f'{prefix}_{id_str}'
        
        # Strip prefix if id_type is None
        return id_str[3:]

    def log_info(self, message: str):
        print(message)
         