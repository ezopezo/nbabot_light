import tweepy
import os
import telebot
import asyncio
from itertools import count
from datetime import datetime, timezone, date, timedelta
from typing import List, Any
import pytz


class GetTweets:
    def __init__(self):
        self.twitter_users = []
        self.telegram_users = []
        self.chat_id = None
        self.created_at_queue = (
            list()
        )  # custom queues for effective looking up, need lookup and ordering
        self.posts_queue = list(("text", "created_at", "timestamp"))

    @property
    def set_twitter_api(self):
        """
        Setting twitter API
        return multiple user objects
        """
        for user_num in count(1, 1):
            consumer_key = os.environ.get(f"CONSUMER_KEY_{user_num}")
            consumer_secret = os.environ.get(f"CONSUMER_SECRET_{user_num}")
            access_key = os.environ.get(f"ACCESS_KEY_{user_num}")
            access_secret = os.environ.get(f"ACCESS_SECRET_{user_num}")
            timeline = os.environ.get(f"TIMELINE_{user_num}")

            if all(consumer_key, consumer_secret, access_key, access_secret, timeline):
                print(f"Setting twitter API for user {user_num}")
                auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
                auth.set_access_token(access_key, access_secret)
                self.twitter_users.append({"user": user_num, "twitter_connection": tweepy.API(auth), "timeline": timeline})
            elif any(
                consumer_key, consumer_secret, access_key, access_secret, timeline
            ) and not all(consumer_key, consumer_secret, access_key, access_secret, timeline):
                print(f"User {user_num} has is missing credentials for building twitter API")
            else:
                print(f"Setup of twitter API done for {str(user_num+1)} users.")
                break
        return self.twitter_users

    @property
    def set_telegram_bot(self):
        """
        Setting telegram bot
        return multiple user objects
        """
        for user_num in count(1, 1):
            bot_token = os.environ.get(f"BOT_TOKEN_{user_num}")
            chat_id = os.environ.get(f"CHAT_ID_{user_num}")
            if all(bot_token, chat_id):
                print(f"Setting telegram API for user {user_num}")
                self.telegram_users.append({"user": user_num, "telegram_connection": telebot.TeleBot(bot_token, parse_mode=None), "chat_id": chat_id})
            elif any(
                bot_token, chat_id
            ) and not all(bot_token, chat_id):
                print(f"User {user_num} has is missing credentials for building telegram API")
            else:
                print(f"Setup of telegram API done for {str(user_num+1)} users.")
                break
        return self.telegram_users

    def obtain_data(self):
        """Obtaining and yielding twitter post(s)"""
        if not self.twitter_users:
            print("Setting twitter API objects...")
            self.twitter_users: List[Any] = self.set_twitter_api

        for user in self.twitter_users:
            post_collection = user["twitter_connection"].user_timeline(
                user["TIMELINE"], count=1, tweet_mode="extended"
            )
            yield from post_collection

    def send_data_to_telegram(self, new_post):
        """Sending data to telegram"""
        if self.telegram_bot is None or self.chat_id is None:
            print("Setting Telegram bot...")
            self.telegram_bot, self.chat_id = self.set_telegram_bot
        for post in self.parse_for_telegram(new_post):
            self.telegram_bot.send_message(self.chat_id, post)
            print("Record sent", new_post, ", parsed to: ", post.replace("\n", " "))

    def parse_for_telegram(self, new_post):
        """Formating data for telegram"""
        formated_post = new_post[0] + "\nCreated at: " + new_post[1]
        yield formated_post

    def set_timestamps(self, post):
        """Adjusting correct timezone in created_at post attribute,
        setting timestamp of post processing"""
        tz = pytz.timezone("Europe/Paris")
        process_time = datetime.now(tz)
        creation_time = (
            post.created_at.replace(tzinfo=timezone.utc)
            .astimezone(tz)
            .strftime("%Y-%m-%d %H:%M:%S")
        )
        return datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S"), process_time

    def maintain_queues(self, max_items_in_queue=20):
        """Controling queue of posts (and created_at queue timestamps)
        for effective memory management"""
        if len(self.posts_queue) > max_items_in_queue:
            del self.posts_queue[0]
            del self.created_at_queue[0]

    def identify_new_post(self):
        """Identifying new post based on conditions:
            1. Avoiding recieving comments of page itself (filtering posts with "@" in beginning)
            2. Storing created_at time in custom queue and comparing every post to avoid duplicities
            3. Not older than 5 minutes to avoid long-term spamming with last tweet in case of twitter down
        Returning new post."""
        for post in self.obtain_data():
            creation_time, processed_time = self.set_timestamps(post)
            if (
                not "@" in post.full_text[0]
                and creation_time not in self.created_at_queue
                and creation_time > datetime.now() - timedelta(seconds=500)
            ):

                self.posts_queue.append(
                    (
                        str(post.full_text),
                        creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                        processed_time.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )

                self.created_at_queue.append(creation_time)
                self.maintain_queues()
                return self.posts_queue[-1]
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
            asyncio.run(control_node(wait_for_next_telegram_check=1.2))
        except Exception as exc:
            print("Bot restarted: ", exc)
            continue


if __name__ == "__main__":
    main()
