from bs4 import BeautifulSoup
import requests
import tweepy
import configparser

import datetime
import os
import re
import random
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = SCRIPT_DIR + '/config.ini'

cf = configparser.RawConfigParser()
cf.read(CONFIG_FILE)
   
# Define path structure and globals
for item in cf['Default'].items():
    globals()[item[0].upper()] = eval(item[1])

# Define Credential variables for accessing Twitter and bit.ly APIs
for item in cf['Credentials'].items():
    globals()[item[0].upper()] = item[1].encode('ascii')
    
        
        
        
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
        
        self.searchTerm = None
        self.searchPage = None
    
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
        search_str = 'Searched tag, page: {0}, {1}\n'.format(self.searchTerm,self.searchPage)
        
        full_str = title_str + name_str + id_str + illustURL_str + short_illustURL_str + photo_str + uploadTime_str + accessTime_str + search_str
        return full_str
        
    def __repr__(self):
        repr_dict = {'site': self.site, 
            'header': self.header, 
            'title': self.title, 
            'imageId': self.imageId, 
            'illustName': self.illustName, 
            'illustId': self.illustId,
            'illustURL': self.illustURL, 
            'uploadTime': self.uploadTime, 
            'photoURL': self.photoURL,
            'accessTime': self.accessTime, 
            'shortURL': self.shortURL,
            'searchTerm': self.searchTerm, 
            'searchPage': self.searchPage
        }
        
        return str(repr_dict)
        
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

    
def fetch_imagelist(page_term, page_num):
    '''Find webpage on Pixiv.  Return HTML content.'''
    SITE_URL = 'http://www.pixiv.net/search.php'
    NUM_REQUEST_ATTEMPTS = 5 # Number of times to attempt to query search page
    
    payload = {
        'word': page_term,
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

    
def parse_images(page, page_term, page_num):
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
        newImage.imageId = imageId
        newImage.uploadTime = uploadTime
        newImage.photoURL = photoURL
        newImage.illustId = illustId
        newImage.illustURL = illustURL
        newImage.accessTime = accessTime
        newImage.searchTerm = page_term
        newImage.searchPage = page_num

        # Add image to list
        image_list.append(newImage)
    
    return image_list

    
def configure_images(cf):
    
    # The config file contains the raw string form of the list of search tags 
    #  and corresponding number of pages, so evaluate them
    SEARCH_TAGS = eval(cf.get('PixivSearch','SEARCH_TAGS'))
    PAGE_LIMS = eval(cf.get('PixivSearch','PAGE_LIMS'))
    DEFAULT_LIM = cf.getint('PixivSearch','DEFAULT_LIM')
    
    # Check integrity of search tags and page limits
    for index,tag in enumerate(SEARCH_TAGS):
        # If PAGE_LIMS is filled with default values (-1), determine maximum page number
        if PAGE_LIMS[index] <= 0:
            page_lim = DEFAULT_LIM
            image_page = fetch_imagelist(tag,str(page_lim))
            while image_page.find('div',{'class':'_no-item'}) is not None:
                # decrement page if last one was empty
                page_lim -= 1
                
                # See if page contains images
                image_page = fetch_imagelist(tag,page_lim)
                
                if page_lim <= 1:
                    print 'Failed to determine page limit for tag: {0}'.format(tag)
                    break
                    
            if page_lim > 1:
                print 'New limit for \'{0}\': {1}'.format(tag,str(page_lim))
                PAGE_LIMS[index] = page_lim
    
    cf.set('PixivSearch','PAGE_LIMS', str(PAGE_LIMS))
    with open(CONFIG_FILE, 'wb') as configOut:
        cf.write(configOut)
        
    return SEARCH_TAGS, PAGE_LIMS
    
   
def main():
       
    ## Process config.ini file
    SEARCH_TAGS, PAGE_LIMS = configure_images(cf)
    
    ## Process and Tweet Images
    image_tweeted = False

    while not image_tweeted:
        try:
            # Randomly select a tag and a page from the configuration file
            selected_index = random.randint(0,len(SEARCH_TAGS)-1)
            selected_tag = SEARCH_TAGS[selected_index]
            selected_page = random.randint(0,PAGE_LIMS[selected_index])
            
            # Get a page of images
            image_page = fetch_imagelist(selected_tag,str(selected_page))
            image_list = parse_images(image_page,selected_tag,selected_page)
            
            # Tweet a random image from list
            random.shuffle(image_list)
            for image in image_list:
                if not image.tweeted_recently():
                    image.post_tweet()
                    image.update_recent_tweets()
                    image_tweeted = True
                    break
        except:
            print 'Failed on {0}, page: {1}.  Retrying...'.format(selected_tag,selected_page)

    # If all images recently tweeted, select image_tweeted at random, post tweet
    if not image_tweeted:
        image = random.choice(image_list)
        image.post_tweet()
        image_tweeted = True

    print image

    
if __name__ == '__main__':
    main()

