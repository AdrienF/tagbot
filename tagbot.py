#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
#sleep in main loop
import time
#wrappers around Slack API
from commonTools import *
#slack API
from slackclient import SlackClient
#url extraction
import re
#database mngmt
import sqlite3
#date
from datetime import date

parser = argparse.ArgumentParser(description = 'Tag bot')
parser.add_argument('slackbot_token', type=str, help='An ID for the slackbot')
parser.add_argument('--database', nargs=1, type=str, default='database.db', help='The name of the database')
args = parser.parse_args()

SLACKBOT_TOKEN = args.slackbot_token
DATABASE = args.database[0]
COMMAND_WORD = 'sum-up'
SLACK_CLIENT ,BOT_ID ,AT_BOT, AT_CHAN = get_slackConstants(SLACKBOT_TOKEN, "tagbot")

MONITORED_REACTIONS_PREFIX = ['flag-','avp','kolor', 'goprovr', 'ptp']

#print('client :', SLACK_CLIENT)
#print('BOT_ID :', BOT_ID)
#print('AT_BOT :', AT_BOT)
#print('AT_CHAN :', AT_CHAN)


def connectToDB(dbName):
    """
    Connect to the database. Eventually create it
    """
    try:
        conn = sqlite3.connect(DATABASE)
    except Exception as e:
        print('connectDB : Unable to connect to {}'.format(DATABASE))
        print('          : {}'.format(e))
        return None

    #create db
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS links(
             link TEXT PRIMARY KEY UNIQUE,
             postedBy TEXT,
             originalMessage TEXT,
             date TEXT,
             tags TEXT,
             channel TEXT
        )
        """)
        conn.commit()
        print( 'table created : {}'.format(DATABASE))
    except sqlite3.OperationalError:
        print('Table already exists')
    except Exception as e:
        print("Error in connectToDB.")
        conn.rollback()
        raise e
    
    return conn

def insertRow(conn, item):
    print('inserting new row : {}', item)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO links(link, postedBy, originalMessage, date, tags, channel) VALUES(:link, :postedBy, :originalMessage, :date, :tags, :channel);""", 
            item)
        conn.commit()
    except sqlite3.Error as e:
        print("insertRow : Database error: {}".format(e))
    except Exception as e:
        print("insertRow : Error : {}".format(e))
        conn.rollback()

def getTagsSet(value):
    """
    Return a set of string tags
    :param value:
    :return:
    """
    return set(value.split(u','))

def setTagsString(tags):
    """
    Form a string from a set of strings
    :param tags:
    :return:
    """
    return ','.join(tags)

def editRow(conn, item):
    print('editing row with new tag')
    cursor = conn.cursor()
    url = item['link']
    cursor.execute("""SELECT tags FROM links WHERE link = ?""",(url,))
    entry = cursor.fetchone()
    print('entry : {}'.format(entry))
    currentTags = getTagsSet(entry[0])
    print('tags for link {} : {}'.format(url, currentTags))
    newtag = item['reaction']
    print('insert a new tag : {}'.format(newtag))
    currentTags.add(newtag)
    try:
        cursor.execute("""UPDATE links SET tags = ? WHERE link = ?""", (setTagsString(currentTags),link,))
        conn.commit()
    except sqlite3.Error as e:
        print("editRow : Database error: {}".format(e))
    except Exception as e:
        print("editRowRow : Error : {}".format(e))
        conn.rollback()

def insertTagInDB(conn, item):
    """
    insert a link and all other info in the db,
    if the link is already present, edit the field to add the tag
    """
    cursor = conn.cursor()
    url = item['link']
    #first look if an entry already exists with this URL
    cursor.execute("""SELECT * FROM links WHERE link = ?""",(url,))
    entry = cursor.fetchone()
    if entry is None:
        #create row from item
        insertRow(conn, item)
    else:
        #edit row from item
        editRow(conn, item)
    return 0

def removeTagFromDB(conn, item):
    """
    search item in DB and remove the item tag from the entry
    """
    print('removing tag {} from row {}'.format(item['reaction'],item['url']))
    cursor = conn.cursor()
    url = item['link']
    cursor.execute("""SELECT tags FROM links WHERE link = ?""",(url,))
    entry = cursor.fetchone()
    print('entry : {}'.format(entry))
    currentTags = getTagsSet(entry[0])
    print('tags for link {} : {}'.format(url, currentTags))
    newtag = item['reaction']
    print('iremove tag : {}'.format(newtag))
    currentTags.remove(newtag)
    try:
        cursor.execute("""UPDATE links SET tags = ? WHERE link = ?""", (setTagsString(currentTags),link,))
        conn.commit()
    except sqlite3.Error as e:
        print("editRow : Database error: {}".format(e))
    except Exception as e:
        print("editRowRow : Error : {}".format(e))
        conn.rollback()


    return 0

def retrieveWeekSummary(conn):
    """
    format the database query from the current week
    """
    printDB(conn)
    return 0

def printDB(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM links""")
        entries = cursor.fetchall()
        print('database content:')
        for e in entries:
            print('    {}'.format(e))
    except  Exception as er:
        print('printDB : Error : {}'.format(er))

def closeDB(conn):
    """
    Close the database
    """
    print('Closing database')
    conn.close()
    return 0

def retrieveMessageContent(user, ts):
    for msg in  getUserMessageReactions(SLACK_CLIENT, user):
        text = msg['text']
        msgTs = msg['ts']
        if msgTs == ts :
            return text
    return ''

def extractURLFromMessage(text):
    #urlregexp = '<http(s)?://.*?>'
    urlregexp = '(?:<)(http(?:s)?://[^|]*)(?:\|?)(.*)(?:>)'
    #group(1) = normalized URL
    #group(2) = typed URL
    match = re.search(urlregexp, text)
    if match:
        return match.group(1)
    else :
        return None

def sumUp(channel, conn):
    """
    Read the db, sum up the current week, generate an html report and post a link to it in the channel.
    :param: channel : the channel in which to post the answer
    :return: nothing
    """
    print('Exectuting command \'sum-up\'')
    if conn:
        retrieveWeekSummary(conn)
    message = 'Sure, will do!'
    SLACK_CLIENT.api_call("chat.postMessage", channel=channel, text=message, as_user=True)

def interceptReactions(channel, reactionObject, prefix, conn):
    if reactionObject is not None:
        reactionName = reactionObject['reaction']
        userReacting = reactionObject['user']
        reactingToItem = reactionObject['item']
        itemAuthor = reactionObject['item_user']
        isAdded = 'reaction_added' == reactionObject['type']

        if reactingToItem['type'] != 'message':
            #only reaction to messages are used
            return

        if isAdded:
            status = 'added'
        else:
            status = 'removed'

        postedInPrivate = False
        channelName = getChannelName(SLACK_CLIENT, channel)
        if  'ChannelUnknown' == channelName :
            postedInPrivate = True
            privateGroup = getPrivateChannelName(SLACK_CLIENT, channel)
            channelName = '-REDACTED-'

        #get the message content
        itemText = retrieveMessageContent(itemAuthor, reactingToItem['ts'])

        #get the link within the message
        url = extractURLFromMessage(itemText)

        if url is None or not url:
            return

        #format the item to feed in the db
        userName = getUserName(SLACK_CLIENT, userReacting) 
        authorName = getUserName(SLACK_CLIENT, itemAuthor) 
        dbItem = {'link' : url,
                  'postedBy' : authorName,
                  'originalMessage' : itemText,
                  'date' : date.today().isoformat(),
                  'tags' : reactionName,
                  'channel' : channelName}
        if conn is not None :
            if isAdded:
                insertTagInDB(conn, dbItem)
            else:
                removeTagFromDB(conn, dbItem)
        else:
            print('Unable to use database, NULL connection')

        message = 'User {} reacted to the message of {} with {} (status is \'{}\') in channel {}'.format(
                userName, 
                authorName, 
                reactionName, 
                status,
                channelName) 
        print(message)
        print('The message : {} contains url : {}'.format(itemText, url))
        #SLACK_CLIENT.api_call(
        #        "chat.postMessage", 
        #        channel=channel, 
        #        text=message,
        #        as_user=True)

#___ Main
if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    try:
        conn = connectToDB(DATABASE)
        print("Listening with a {} second delay".format(READ_WEBSOCKET_DELAY))
        if SLACK_CLIENT.rtm_connect():
            print("tagbot connected and running!")
            while True:
                rtm_output = SLACK_CLIENT.rtm_read()
                #monitor messages adressed to the bot
                command, channel = parse_slack_message(rtm_output,AT_BOT)
                if command is not None and channel is not None:
                    print('command : {}; channel : {}'.format(command, channel))
                    if command.startswith(COMMAND_WORD):
                        sumUp(channel, conn)
                #monitor reactions to message
                for prefix, reaction in parse_slack_reactions(rtm_output, MONITORED_REACTIONS_PREFIX ):
                    interceptReactions(channel, reaction, prefix, conn)
                #sleep
                time.sleep(READ_WEBSOCKET_DELAY)
        else:
            print("Connection failed. Invalid Slack token or bot ID?")
    except Exception as e:
        print('Something wrong happened : {}'.format(e))
        conn.rollback()
    finally:
        closeDB(conn)

