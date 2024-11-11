# Generated by Django 4.2 on 2024-11-11 09:20
import time

from praw import Reddit
import prawcore

from django.conf import settings
from django.db import migrations, models


    
instance_values = {
    "Comment": {},
    "Submission": {},
}


def get_distinguished_values(apps, schema_editor):
    Comment = apps.get_model('collector', 'Comment')
    Submission = apps.get_model('collector', 'Submission')

    reddit_interface = Reddit(
            client_id=settings.REDDIT_API_CLIENT_ID,
            client_secret=settings.REDDIT_API_CLIENT_SECRET,
            password=settings.REDDIT_ACCOUNT_PASSWORD,
            user_agent="LLM_use_case_tracker/1.0",
            username=settings.REDDIT_ACCOUNT_USERNAME,
        )


    for comment in Comment.objects.filter(distinguished=True):
        # comment.distinguished = None
        # comment.save()
        try:
            praw_comment = reddit_interface.comment(comment.reddit_id)
            instance_values["Comment"][comment.reddit_id] = praw_comment.distinguished
            time.sleep(3)  # Prevent too many requests
        except Exception as e:
            print(f"Error processing comment {comment.reddit_id}: {str(e)}")

    

    for submission in Submission.objects.filter(distinguished=True):
        # submission.distinguished = None
        # submission.save()
        try:
            praw_submission = reddit_interface.submission(submission.reddit_id)
            instance_values["Submission"][submission.reddit_id] = praw_submission.distinguished
            time.sleep(3)  # Prevent too many requests
        except Exception as e:
            print(f"Error processing submission {submission.reddit_id}: {str(e)}")


def set_actual_distinguished_values(apps, schema_editor):
    Comment = apps.get_model('collector', 'Comment')
    Submission = apps.get_model('collector', 'Submission')

    reddit_interface = Reddit(
            client_id=settings.REDDIT_API_CLIENT_ID,
            client_secret=settings.REDDIT_API_CLIENT_SECRET,
            password=settings.REDDIT_ACCOUNT_PASSWORD,
            user_agent="LLM_use_case_tracker/1.0",
            username=settings.REDDIT_ACCOUNT_USERNAME,
        )

    for comment in Comment.objects.filter(reddit_id__in=instance_values["Comment"].keys()):
        value = instance_values["Comment"][comment.reddit_id]
        comment.distinguished = value
        comment.save()
    

    for submission in Submission.objects.filter(reddit_id__in=instance_values["Submission"].keys()):
        value = instance_values["Submission"][submission.reddit_id]
        submission.distinguished = value
        submission.save()


class Migration(migrations.Migration):

    dependencies = [
        ('collector', '0002_added_modified_dt'),
    ]

    operations = [
        migrations.RunPython(
            get_distinguished_values,
            None,
        ),
        migrations.AlterField(
            model_name='comment',
            name='distinguished',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='submission',
            name='distinguished',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.RunPython(
            set_actual_distinguished_values,
            None,
        ),
    ]