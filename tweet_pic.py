from bs4 import BeautifulSoup
import requests
import tweepy

import datetime
import os
import re
import random
import time

from credentials import CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET, BITLY_TOKEN
from search_terms import SEARCH_DICT

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
IMAGE_PATH = SCRIPT_DIR + '/Downloaded_Images'
RECENT_TWEETS_FILE = SCRIPT_DIR + '/recent_tweets.dat'
NUM_RECENT_TWEETS = 200 # Number of recent posts to track

class TwitterAPI(object):

    def __init__(self): 
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
        self.api = tweepy.API(auth)
    
    def tweet(self, message):
        self.api.update_status(status=message)

    def tweet_with_img(self, img_path, msg):
        self.api.update_with_media(filename=img_path, status=msg)


class Image(object):

    def __init__(self):
        self.site = 'http://www.pixiv.net'
        self.header = {'referer':self.site}
    
        self.title = None
        self.imageId = None
        self.illustName = None
        self.illustId = None
        self.illustURL = None
        self.uploadTime = None
        self.photoURL = None
        self.accessTime = None
        self.shortURL = None
        
    def __str__(self):
        title_str = 'Title: {0}\n'.format(self.title.encode('utf-8'))
        imageId_str = 'ID: {0}\n'.format(self.imageId.encode('utf-8'))
        name_str = 'Illustrator: {0}\n'.format(self.illustName.encode('utf-8'))
        id_str = 'Illustrator ID: {0}\n'.format(self.illustId)
        illustURL_str = 'Illustrator\'s Page: {0},\t'.format(self.site + self.illustURL)
        short_illustURL_str = 'Shortned: {0}\n'.format(self.shortURL)
        photo_str = 'Photo URL: {0}\n'.format(self.photoURL)
        uploadTime_str = 'Uploaded on: {0}\n'.format(self.uploadTime.ctime())
        accessTime_str = 'First accessed on: {0}\n'.format(self.accessTime.ctime())
        
        full_str = title_str + name_str + id_str + illustURL_str + short_illustURL_str + photo_str + uploadTime_str + accessTime_str
        return full_str

    def get_image(self):
        '''Download image, write to local file'''
        if not os.path.exists(IMAGE_PATH):
            os.makedirs(IMAGE_PATH)
            
        # Tweepy doesn't currently support unicode strings!  So use the ascii ID as a workaround
        #LOCAL_IMG_FILE = IMAGE_PATH + '/' + self.title.encode('utf-8') + '.jpg'
        
        LOCAL_IMG_FILE = IMAGE_PATH + '/' + self.imageId + '.jpg'
        
        res = requests.get(self.photoURL.encode('ascii'), headers=self.header)
        
        with open(LOCAL_IMG_FILE, 'wb') as f:
            f.write(res.content)
        return LOCAL_IMG_FILE

    def shorten_illust_url(self):
        shorten_url = 'https://api-ssl.bitly.com/v3/shorten'
        payload = {'access_token': BITLY_TOKEN, 'longUrl': (self.site + self.illustURL).encode('ascii'), 'domain':'bit.ly'}
        res = requests.get(shorten_url, params = payload)
        try:
            self.shortURL = res.json()['data']['url']
            return self.shortURL
        except:
            return None

    def post_tweet(self):
        '''Get image, format tweet, post tweet'''
        twitter = TwitterAPI()
        LOCAL_IMG_FILE = self.get_image()
        shortURL = self.shorten_illust_url()
        
        # Twitter uses a url shortner which removes the php request for the illustrator
        # tweetMsg = '{0} (id: {1}, {2}) - {3}. '.format(self.illustName.encode('utf-8'), self.illustId, self.site + self.illustURL, self.title.encode('utf-8'))
        
        # Too cumbersome
        # tweetMsg = '{0} (id: {1}) - Title: {2}.  Illust: {3}'.format(self.illustName.encode('utf-8'), self.illustId, self.title.encode('utf-8'), shortURL)
        
        if shortURL is not None:
            tweetMsg = '{0} - {1}.  Illustrator: {2}'.format(self.illustName.encode('utf-8'), self.title.encode('utf-8'), shortURL)
        else:
            tweetMsg = '{0} - {1}.'.format(self.illustName.encode('utf-8'), self.title.encode('utf-8'))
 
        twitter.tweet_with_img(LOCAL_IMG_FILE, tweetMsg)

    def tweeted_recently(self):
        '''Check to determine whether image has been tweeted recently''' 
        return self.photoURL in get_recent_tweets()

    def update_recent_tweets(self):
        '''Write profile URL to list of recent tweets'''       
        recent_tweets = get_recent_tweets()
        recent_tweets.append(self.photoURL)

        while len(recent_tweets) > NUM_RECENT_TWEETS:
            recent_tweets.pop(0)
        
        with open(RECENT_TWEETS_FILE, 'w') as f:
            for item in recent_tweets:
                f.write('{0}\n'.format(item))


def get_recent_tweets():
    '''Return list of URLs to recently tweeted images'''
    # Get recent tweets from local file if they exist
    if os.path.isfile(RECENT_TWEETS_FILE):
        with open(RECENT_TWEETS_FILE, 'r') as f:
            recent_tweets = f.read().splitlines()
    else:
        recent_tweets = []

    return recent_tweets

def fetch_imagelist(page_num):
    '''Find webpage on Pixiv.  Return HTML content.'''
    SITE_URL = 'http://www.pixiv.net/search.php'
    NUM_REQUEST_ATTEMPTS = 5 # Number of times to attempt to query search page


    payload = {
        'word': SEARCH_DICT['tags'],
        's_mode': 's_tag_full',
        'order': 'date_d', 
        'p': page_num
    }

    # Get and parse page
    for attempt in range(NUM_REQUEST_ATTEMPTS):
        try:
            res = requests.get(SITE_URL, params=payload, timeout=5)
            break
        except:
            time.sleep(5) # Wait 5 seconds before trying again

    page = BeautifulSoup(res.content,"html.parser")
    return page

    
def parse_images(page):
    '''Extract content from Pixiv page, return a list of Image objects'''
    image_list = []
    
    for thumbnails in page.find_all('li',{'class':'image-item'}):
    
        # Initialize Image
        newImage = Image()

        # Get Image Title
        title = thumbnails.h1.attrs['title']
        
        # get Illustrator
        illustElement = thumbnails.find('a',{'class':'user'})
        
        illustName = illustElement.text
        illustId = illustElement.get('data-user_id')
        illustURL = illustElement.attrs['href']

        # Get Date Uploaded
        upload_date_link = thumbnails.img.attrs['src'].split('img/')[1].split('_')[0]

        # Get Image ID
        imageId = upload_date_link.split('/')[-1]
        
        # datetime only accepts 6 microsecond digits
        uploadTime = datetime.datetime(*map(int, re.split('[^\d]', upload_date_link[:upload_date_link.find(imageId)])[:-1]))
        
        # get access time
        accessTime = datetime.datetime.now()
        
        # Get photo URL
        photoURL = thumbnails.img.attrs['src']
        
        # Use the medium-size images instead of thumbnails
        photoURL = photoURL.replace('150x150','600x600')
        
        # Set image attributes
        newImage.title = title
        newImage.illustName = illustName
        newImage.uploadTime = uploadTime
        newImage.photoURL = photoURL
        newImage.illustId = illustId
        newImage.illustURL = illustURL
        newImage.accessTime = accessTime
        newImage.imageId = imageId

        # Add image to list
        image_list.append(newImage)
    
    return image_list


def main():
    image_tweeted = False

    while not image_tweeted:
        # Get a page of images
        image_page = fetch_imagelist(random.randint(0,SEARCH_DICT['page_lim']))
        image_list = parse_images(image_page)

        # Tweet a random image from list
        random.shuffle(image_list)
        for image in image_list:
            if not image.tweeted_recently():
                image.post_tweet()
                image.update_recent_tweets()
                image_tweeted = True
                break

    # If all images recently tweeted, select image_tweeted at random, post tweet
    if not image_tweeted:
        image = random.choice(image_list)
        image.post_tweet()
        image_tweeted = True

    print image

if __name__ == '__main__':
    main()

