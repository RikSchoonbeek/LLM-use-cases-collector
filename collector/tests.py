from praw import Reddit

from django.conf import settings
from django.test import TestCase

from collector.clients import RedditAPIClient

# Create your tests here.
class TempTestCase(TestCase):

    def test_1(self):
        # client = RedditAPIClient()
        # client.retrieve_subreddit_threads(subreddit_name="ArtificialInteligence")
        # reddit = Reddit(
        #     client_id=settings.REDDIT_API_CLIENT_ID,
        #     client_secret=settings.REDDIT_API_CLIENT_SECRET,
        #     password=settings.REDDIT_ACCOUNT_PASSWORD,
        #     user_agent="LLM_use_case_tracker/1.0",
        #     username=settings.REDDIT_ACCOUNT_USERNAME,
        # )

        # get access to subreddit: reddit.subreddit("ArtificialInteligence")
        # get acces to subreddit submissions (threads/posts):
        #  - subreddit.new(limit=100) (can also use hot and other option(s))


        