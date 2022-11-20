import os
import asyncio

from typing import List, Tuple
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone, timedelta

import pytz
import telebot
import tweepy

tz = pytz.timezone("Europe/Paris")


@dataclass
class Tweet:
    """Tweet dataclass."""

    post: object
    creation_time: datetime
    processing_time: datetime = datetime.now(tz)

    @property
    def full_text(self) -> str:
        return str(self.post.full_text)

    @property
    def str_processed_time(self) -> str:
        return self.processing_time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def str_creation_time(self) -> str:
        return self.substitute_timezone().strftime("%Y-%m-%d %H:%M:%S")

    @property
    def obj_creation_time(self) -> datetime:
        return self.substitute_timezone()

    def substitute_timezone(self):
        return self.creation_time.replace(tzinfo=pytz.utc).astimezone(tz)


class TweetQueue:
    def __init__(self) -> None:
        self.items = deque(maxlen=20)

    @property
    def creation_times_queue(self) -> List[str]:
        return [t.str_creation_time for t in self.items]

    def enqueue(self, item) -> None:
        self.items.append(item)

    def get_new_tweet(self) -> Tweet:
        return self.items[-1]

word_emoticon_mapping = {
    "ruled out": 5 * "\U0000274C" + " \"ruled out\"",  # cross mark
    "doubtful": 5 * "\U0001F534" + " \"doubtful\"",  # red circle
    "questionable": 3 * "\U0001F7E0" + " \"questionable\"",  # orange circle
    "probable": 3 * "\U0001F7E1" + " \"probable\"",  # yellow circle
    "expected to play": 3 * "\U0001F7E1" + " \"expected to play\"",  # yellow circle
    "available to play": 3 * "\U0001F7E2" + " \"available to play\"",  # green circle
    "will play": 3 * "\U0001F7E2" + " \"will play\"",  # green circle
    "will start": 3 * "\U0001F7E2" + " \"will start\"",  # green circle
    "a game-time decision": 3 * "\U0001F535" + " \"a game-time decision \"",  # blue circle
    "bench": "\U00002753" + " \"bench\"",  # red question mark
    "limit": 2 * "\U00002753" + " \"limit\"",  # red question mark
    "expects": 3 * "\U0001F7E0" + " \" expects\"",  # orange circle
    "likely to play": 3 * "\U0001F7E1" + " \"likely to play\"",  # yellow circle
    "unlikely to play": 3 * "\U0001F7E0" + " \" unlikely to play\"",  # orange circle
    "listed out": 5 * "\U0000274C" + " \"listed out\""  # cross mark
}


class GetTweets:
    def __init__(self):
        self.twitter_api = None
        self.telegram_bot = None
        self.posts_queue = TweetQueue()

    @property
    def set_twitter_api(self):
        """Setting twitter API"""
        auth = tweepy.OAuthHandler(
            os.environ["CONSUMER_KEY"], os.environ["CONSUMER_SECRET"]
        )
        auth.set_access_token(os.environ["ACCESS_KEY"], os.environ["ACCESS_SECRET"])
        twitter_api = tweepy.API(auth)
        return twitter_api

    @property
    def set_telegram_bot(self):
        """Setting telegram bot"""
        bot_token = os.environ["BOT_TOKEN"]
        chat_id = os.environ["CHAT_ID"]
        telegram_bot = telebot.TeleBot(bot_token, parse_mode=None)
        return telegram_bot, chat_id

    def obtain_data(self):
        """Obtaining and yielding twitter post(s)"""
        if self.twitter_api is None:
            print("Setting twitter API connection...")
            self.twitter_api = self.set_twitter_api
        post_collection = self.twitter_api.user_timeline(
            os.environ.get("TIMELINE"), count=1, tweet_mode="extended"
        )
        yield from post_collection
    
    def add_emoticons(self, post):
        changed_post = post.lower()
        emoticons = ""
        for key_word, emoticon in word_emoticon_mapping.items():
            if key_word in changed_post:
                emoticons = emoticons + emoticon + "\n"
        new_post = emoticons + post
        return new_post

    def parse_for_telegram(self, new_tweet):
        """Formating data for telegram"""
        formated_post = (
            str(new_tweet.full_text) + "\nCreated at: " + new_tweet.str_creation_time
        )
        return formated_post

    def send_data_to_telegram(self, new_post):
        """Sending data to telegram"""
        if self.telegram_bot is None:
            print("Setting Telegram bot...")
            self.telegram_bot, self.chat_id = self.set_telegram_bot
        formated_post = self.parse_for_telegram(new_post)
        decorated_post = self.add_emoticons(formated_post)
        self.telegram_bot.send_message(self.chat_id, decorated_post)
        print(
            f"Record sent. Processed: {new_post.str_processed_time} | "
            f"Created: {new_post.str_creation_time} | Text:\n {decorated_post}"
        )

    def identify_new_post(self):
        """Identifying new post based on conditions:
            1. Avoiding recieving comments of page itself (filtering posts with "@" in beginning)
            2. Storing created_at time in custom queue and comparing every post to avoid duplicities
            3. Not older than 5 minutes to avoid long-term spamming with last tweet in case of twitter downtime
        Returning new post."""
        for post in self.obtain_data():
            tweet = Tweet(post, post.created_at)
            if (
                not "@" in tweet.full_text
                and tweet.str_creation_time not in self.posts_queue.creation_times_queue
                and tweet.obj_creation_time
                > datetime.now(tz)
                - timedelta(seconds=int(os.environ.get("NOT_OLDER_THAN_SEC", 500)))
            ):
                self.posts_queue.enqueue(tweet)
                return self.posts_queue.get_new_tweet()
            else:
                return None


async def control_node(wait_for_next_telegram_check):
    """If new post identified, it is passed for telegram processing"""
    get_tweets = GetTweets()
    while True:
        await asyncio.sleep(wait_for_next_telegram_check)
        new_post = get_tweets.identify_new_post()
        if new_post:
            get_tweets.send_data_to_telegram(new_post)


def main():
    while True:
        try:
            asyncio.run(
                control_node(
                    wait_for_next_telegram_check=float(
                        os.environ.get("WAIT_PERIOD", 1.2)
                    )
                )
            )
        except Exception as exc:
            print("Bot restarted: ", exc)
            continue


if __name__ == "__main__":
    main()
