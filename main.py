import tweepy
import os
import telebot 
import asyncio
from datetime import datetime, timezone
import pytz

posts = [('text', 'created_at', 'timestamp')]

def set_api():
    auth = tweepy.OAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
    auth.set_access_token(os.environ['ACCESS_KEY'], os.environ['ACCESS_SECRET'])
    api = tweepy.API(auth)
    return api


def set_bot():
    bot_token = os.environ['BOT_TOKEN']
    chat_id = os.environ['CHAT_ID']
    bot = telebot.TeleBot(bot_token, parse_mode=None)
    return bot, chat_id


def obtain_data():
    api = set_api()
    global posts
    post_iterator = api.user_timeline("FantasyLabsNBA", count=1)
    for post in post_iterator:
        yield post


def parse_for_telegram(new_post):
    formated_post = new_post[0] + '\nCreated: ' + new_post[1]
    yield formated_post


def send_data_to_telegram(new_post):
    bot, chat_id = set_bot()
    for post in parse_for_telegram(new_post):
        bot.send_message(chat_id, post)


def identify_new_post():
    last_post = posts[-1]
    tz = pytz.timezone('Europe/Paris') # <- put your local timezone here
    for post in obtain_data():
        if post.text != last_post[0]:
            posts.append((str(post.text), 
                            post.created_at.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
                            datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")))
            if len(posts) > 10:
                del posts[0] 
            return posts[-1]
        else:
            return None


async def control_node(wait_for):
    while True:
        await asyncio.sleep(wait_for)
        new_post = identify_new_post()
        if new_post:
            print('New record found: ', new_post)
            send_data_to_telegram(new_post)
        else:
            pass


if __name__ == '__main__':
    while True:
        try:
            asyncio.run(control_node(2))
        except Exception as e:
            print(e)
            bot, chat_id = set_bot()
            bot.send_message(chat_id, 'Bot succesfully restarted... Last tweet may reappear.')
            continue