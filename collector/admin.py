from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import (
    InformationToDetect,
    Redditor,
    Subreddit,
    Submission,
    Comment,
    DetectedInformation,
    PydanticResponseFormat,
    PydanticResponseFormatField,
)


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


class PydanticResponseFormatFieldInline(admin.TabularInline):
    model = PydanticResponseFormatField
    extra = 1
    readonly_fields = ('created_dt', 'modified_dt')


@admin.register(PydanticResponseFormat)
class PydanticResponseFormatAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_dt', 'modified_dt')
    search_fields = ('name',)
    readonly_fields = ('created_dt', 'modified_dt')
    inlines = [PydanticResponseFormatFieldInline]


@admin.register(PydanticResponseFormatField)
class PydanticResponseFormatFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_model', 'data_type', 'created_dt', 'modified_dt')
    list_filter = ('data_type', 'base_model')
    search_fields = ('name', 'base_model__name')
    readonly_fields = ('created_dt', 'modified_dt')


@admin.register(InformationToDetect)
class InformationToDetectAdmin(admin.ModelAdmin):
    list_display = ('id', 'response_format', 'truncated_instruction')
    list_filter = ('response_format',)
    search_fields = ('llm_instruction_message', 'response_format__name')
    raw_id_fields = ('response_format',)

    def truncated_instruction(self, obj):
        return obj.llm_instruction_message[:100] + '...' if len(obj.llm_instruction_message) > 100 else obj.llm_instruction_message
    truncated_instruction.short_description = 'Instruction Message'


@admin.register(DetectedInformation)
class DetectedInformationAdmin(admin.ModelAdmin):
    list_display = ('submission', 'information_tsf', 'created_dt', 'modified_dt')
    list_filter = ('information_tsf', 'created_dt')
    search_fields = ('submission__id', 'information_tsf__llm_instruction_message')
    raw_id_fields = ('submission', 'information_tsf')
    readonly_fields = ('created_dt', 'modified_dt')
