from django.db import models
from mptt.models import MPTTModel, TreeForeignKey
from django.utils import timezone

class Redditor(models.Model):
    username = models.CharField(max_length=255, unique=True)
    created_utc = models.DateTimeField(null=True)

class Subreddit(models.Model):
    name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    description_html = models.TextField(blank=True)
    public_description = models.TextField(blank=True)
    created_utc = models.DateTimeField(null=True)
    over_18 = models.BooleanField(default=False)
    subscribers = models.PositiveIntegerField(default=0)
    can_assign_link_flair = models.BooleanField(default=False)
    can_assign_user_flair = models.BooleanField(default=False)
    spoilers_enabled = models.BooleanField(default=True)

class Submission(models.Model):
    reddit_id = models.CharField(max_length=50, unique=True)
    author = models.ForeignKey(Redditor, on_delete=models.CASCADE, blank=True, null=True)
    subreddit = models.ForeignKey(Subreddit, on_delete=models.CASCADE)
    title = models.CharField(max_length=500)
    selftext = models.TextField(blank=True)
    url = models.URLField(max_length=2000, blank=True)
    created_utc = models.DateTimeField()
    score = models.IntegerField(default=0)
    upvote_ratio = models.FloatField(default=1.0)
    num_comments = models.PositiveIntegerField(default=0)
    over_18 = models.BooleanField(default=False)
    spoiler = models.BooleanField(default=False)
    stickied = models.BooleanField(default=False)
    distinguished = models.BooleanField(default=False, null=True)
    edited_utc = models.DateTimeField(blank=True, null=True)
    locked = models.BooleanField(default=False)
    saved = models.BooleanField(default=False)
    is_original_content = models.BooleanField(default=False)
    is_self = models.BooleanField(default=False)
    permalink = models.CharField(max_length=500)
    author_flair_text = models.CharField(max_length=255, blank=True, null=True)
    link_flair_text = models.CharField(max_length=255, blank=True, null=True)
    link_flair_template_id = models.CharField(max_length=255, blank=True, null=True)

class Comment(MPTTModel):
    """
    Represents Comment instance as provided by the Reddit API.
    https://praw.readthedocs.io/en/stable/code_overview/models/comment.html
    """
    reddit_id = models.CharField(max_length=50, unique=True)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Redditor, on_delete=models.CASCADE, blank=True, null=True)
    body = models.TextField()
    body_html = models.TextField()
    created_utc = models.DateTimeField()
    score = models.IntegerField(default=0)
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    distinguished = models.BooleanField(default=False)
    edited_utc = models.DateTimeField(blank=True, null=True)
    stickied = models.BooleanField(default=False)
    saved = models.BooleanField(default=False)
    is_submitter = models.BooleanField(default=False)
    permalink = models.CharField(max_length=500)

    class MPTTMeta:
        order_insertion_by = ['created_utc']
