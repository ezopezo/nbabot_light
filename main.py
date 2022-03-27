import tweepy
import os
import telebot 
import asyncio
from datetime import datetime, timezone, date, timedelta
import pytz


class GetTweets:
    def __init__(self):
        self.twitter_api = None
        self.telegram_bot = None
        self.chat_id = None
        self.created_at_queue = list() # custom queues for effective looking up, need lookup and ordering
        self.posts_queue = list(('text', 'created_at', 'timestamp'))


    @property
    def set_twitter_api(self):
        '''Setting twitter API'''
        auth = tweepy.AppAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
        twitter_api = tweepy.API(auth)
        return twitter_api


    @property
    def set_telegram_bot(self):
        '''Setting telegram bot'''
        bot_token = os.environ['BOT_TOKEN']
        chat_id = os.environ['CHAT_ID']
        telegram_bot = telebot.TeleBot(bot_token, parse_mode=None)
        return telegram_bot, chat_id


    def obtain_data(self):
        '''Obtaining and yielding twitter post(s)'''
        if self.twitter_api is None:
            print('Setting twitter API connection...')
            self.twitter_api = self.set_twitter_api
        post_collection = self.twitter_api.user_timeline(os.environ.get("TIMELINE"), count=1, tweet_mode='extended')
        yield from post_collection


    def parse_for_telegram(self, new_post):
        '''Formating data for telegram'''
        formated_post = new_post[0] + '\nCreated at: ' + new_post[1]
        yield formated_post


    def send_data_to_telegram(self, new_post):
        '''Sending data to telegram'''
        if self.telegram_bot is None or self.chat_id is None:
            print('Setting Telegram bot...')
            self.telegram_bot, self.chat_id = self.set_telegram_bot
        for post in self.parse_for_telegram(new_post):
            self.telegram_bot.send_message(self.chat_id, post)
            print('Record sent', new_post, ', parsed to: ', post.replace('\n', ' '))


    def set_timestamps(self, post):
        '''Adjusting correct timezone in created_at post attribute,
        setting timestamp of post processing'''
        tz = pytz.timezone('Europe/Paris')
        process_time = datetime.now(tz)
        creation_time = post.created_at.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        return datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S"), process_time


    def maintain_queues(self, max_items_in_queue=20):
        '''Controling queue of posts (and created_at queue timestamps) 
        for effective memory management'''
        if len(self.posts_queue) > max_items_in_queue:
            del self.posts_queue[0] 
            del self.created_at_queue[0]


    def identify_new_post(self):
        '''Identifying new post based on conditions:
            1. Avoiding recieving comments of page itself (filtering posts with "@" in beginning)
            2. Storing created_at time in custom queue and comparing every post to avoid duplicities 
            3. Not older than 5 minutes to avoid long-term spamming with last tweet in case of twitter down
        Returning new post.'''
        for post in self.obtain_data():
            creation_time, processed_time = self.set_timestamps(post)
            if not '@' in post.full_text[0] \
                and creation_time not in self.created_at_queue \
                and creation_time > datetime.now()-timedelta(seconds=500):

                self.posts_queue.append((str(post.full_text), 
                                creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                                processed_time.strftime("%Y-%m-%d %H:%M:%S")))

                self.created_at_queue.append(creation_time)
                self.maintain_queues()
                return self.posts_queue[-1]
            else:
                return None



async def control_node(wait_for_next_telegram_check):
    '''If new post identified, it is passed for telegram processing '''
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
            print('Bot restarted: ', exc)
            continue


if __name__ == '__main__':
    main()