import tweepy
import os
import telebot 
import asyncio
from datetime import datetime, timezone, date
import pytz


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
    post_iterator = api.user_timeline("FantasyLabsNBA", count=1)
    for post in post_iterator:
        yield post


def parse_for_telegram(new_post):
    formated_post = new_post[0] + '\nCreated at: ' + new_post[1]
    yield formated_post


def send_data_to_telegram(new_post):
    bot, chat_id = set_bot()
    for post in parse_for_telegram(new_post):
        bot.send_message(chat_id, post)


def identify_new_post(posts_queue, created_at_queue):
    tz = pytz.timezone('Europe/Paris')
    for post in obtain_data():
        creation_time = post.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
        process_time = datetime.now(tz)
        if creation_time.date() == process_time.date() and \
            not '@' in post.text[0] and \
            creation_time not in created_at_queue: # avoiding duplicities
            posts_queue.append((str(post.text), 
                            creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                            process_time.strftime("%Y-%m-%d %H:%M:%S")))
            created_at_queue.append(creation_time)
            if len(posts_queue) > 20:
                del posts_queue[0] 
                del created_at_queue[0]
            return posts_queue[-1]
        else:
            return None


async def control_node(wait_for, posts_queue, created_at_queue):
    while True:
        await asyncio.sleep(wait_for)
        new_post = identify_new_post(posts_queue, created_at_queue)
        if new_post:
            print('New record found: ', new_post)
            send_data_to_telegram(new_post)
        else:
            pass


def main():
    while True:
        try:
            created_at_queue = list()
            posts_queue = [('text', 'created_at', 'timestamp')]
            asyncio.run(control_node(2, posts_queue, created_at_queue))
        except Exception as e:
            print(e)
            bot, chat_id = set_bot()
            bot.send_message(chat_id, 'Bot succesfully restarted... Last tweet may reappear.')
            continue

if __name__ == '__main__':
    main()
    