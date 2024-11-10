from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import Redditor, Subreddit, Submission, Comment


@admin.register(Redditor)
class RedditorAdmin(admin.ModelAdmin):
    list_display = ('username', 'created_utc')
    search_fields = ('username',)
    ordering = ('-created_utc',)


@admin.register(Subreddit)
class SubredditAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'subscribers', 'created_utc', 'over_18')
    list_filter = ('over_18', 'can_assign_link_flair', 'can_assign_user_flair', 'spoilers_enabled')
    search_fields = ('name', 'display_name', 'description')
    ordering = ('-subscribers',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('reddit_id', 'title', 'author', 'subreddit', 'score', 'created_utc')
    list_filter = (
        'over_18',
        'spoiler',
        'stickied',
        'distinguished',
        'edited_utc',
        'locked',
        'saved',
        'is_original_content',
        'is_self'
    )
    search_fields = ('title', 'selftext', 'author__username', 'subreddit__name')
    raw_id_fields = ('author', 'subreddit')
    ordering = ('-created_utc',)


@admin.register(Comment)
class CommentAdmin(MPTTModelAdmin):
    list_display = ('reddit_id', 'author', 'submission', 'score', 'created_utc')
    list_filter = (
        'distinguished',
        'edited_utc',
        'stickied',
        'saved',
        'is_submitter'
    )
    search_fields = ('body', 'author__username', 'submission__title')
    raw_id_fields = ('author', 'submission', 'parent')
    ordering = ('-created_utc',)
    mptt_level_indent = 20
