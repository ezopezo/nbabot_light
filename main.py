import tweepy
import os
import telebot 
import asyncio
from datetime import datetime, timezone, date
import pytz


def set_api():
    '''Setting twitter API'''
    auth = tweepy.OAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
    auth.set_access_token(os.environ['ACCESS_KEY'], os.environ['ACCESS_SECRET'])
    api = tweepy.API(auth)
    return api


def set_bot():
    '''Setting telegram bot'''
    bot_token = os.environ['BOT_TOKEN']
    chat_id = os.environ['CHAT_ID']
    bot = telebot.TeleBot(bot_token, parse_mode=None)
    return bot, chat_id


def obtain_data():
    '''Obtaining and yielding twitter post(s)'''
    api = set_api()
    post_collection = api.user_timeline("FantasyLabsNBA", count=1)
    yield from post_collection


def parse_for_telegram(new_post):
    '''Formating data for telegram'''
    formated_post = new_post[0] + '\nCreated at: ' + new_post[1]
    yield formated_post


def send_data_to_telegram(new_post):
    '''Sending data to telegram'''
    bot, chat_id = set_bot()
    for post in parse_for_telegram(new_post):
        bot.send_message(chat_id, post)


def set_timestamps(post):
    '''Adjusting correct timezone in created_at post attribute,
    setting timestamp of post processing'''
    tz = pytz.timezone('Europe/Paris')
    creation_time = post.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
    process_time = datetime.now(tz)
    return creation_time, process_time


def control_queues(posts_queue, created_at_queue, max_items_in_queue=20):
    '''Controling queue of posts (and created_at queue timestamps) 
    for effective memory management'''
    if len(posts_queue) > max_items_in_queue:
        del posts_queue[0] 
        del created_at_queue[0]


def identify_new_post(posts_queue, created_at_queue):
    '''Identifying new post based on conditions:
        1. Post from same day (avoiding different day artefacts)
        2. Avoiding recieving comments of page itself (filtering posts with "@" in beginning)
        3. Storing created_at time in custom queue and comparing every post to avoid duplicities 
       Returning new post.'''
    for post in obtain_data():
        creation_time, process_time = set_timestamps(post)
        if creation_time.date() == process_time.date() and \
            not '@' in post.text[0] and \
            creation_time not in created_at_queue:

            posts_queue.append((str(post.text), 
                            creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                            process_time.strftime("%Y-%m-%d %H:%M:%S")))

            created_at_queue.append(creation_time)
            control_queues(posts_queue, created_at_queue)
            return posts_queue[-1]
        else:
            return None


async def control_node(wait_for, posts_queue, created_at_queue):
    '''If new past identified, it is logged and redirected for telegram processing '''
    while True:
        await asyncio.sleep(wait_for)
        new_post = identify_new_post(posts_queue, created_at_queue)
        if new_post:
            print('New record found: ', new_post)
            send_data_to_telegram(new_post)


def main():
    while True:
        try:
            created_at_queue = list() # custom queues for effective looking up
            posts_queue = list(('text', 'created_at', 'timestamp'))
            asyncio.run(control_node(wait_for=1.2, posts_queue=posts_queue, created_at_queue=created_at_queue))
        except Exception as exc:
            print('Bot restarted: ', exc)
            bot, chat_id = set_bot()
            bot.send_message(chat_id, 'Bot succesfully restarted... Last tweet may reappear.')
            continue


if __name__ == '__main__':
    main()
    