#!/usr/bin/env python
# -*- coding: utf-8 -*-

from slackclient import SlackClient

def get_botID(slack_client, name):
    api_call = slack_client.api_call("users.list")
    if api_call.get('ok'):
        # retrieve all users so we can find our bot
        users = api_call.get('members')
        for botuser in getFastBotUser(api_call.get('members'), name):
            if botuser:
                return botuser.get('id')
            else:
                return None
    else:
        return None

def getFastBotUser(users, botname):
    for user in users:
        if 'name' in user and user.get('name') == botname:
            yield user
    yield None


#___ Slack Constants
def get_slackConstants(slackbot_token, name):
    SLACK_CLIENT = SlackClient(slackbot_token)
    BOT_ID = get_botID(SLACK_CLIENT, name)
    AT_BOT = "<@" + BOT_ID + "> "
    AT_CHAN = "<!channel> "
    return  SLACK_CLIENT,BOT_ID,AT_BOT,AT_CHAN

#___ Functions
def parse_slack_message(slack_rtm_output, AT_BOT):
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            t = output['type']
            if t == 'message':
                text = output['text']
                channel = output['channel']
                print('intercepted in {} : {}'.format(channel, text))
                if AT_BOT in text :
                    return text.split(AT_BOT)[1].strip().lower(), channel

    return None, None

def parse_slack_reactions(slack_rtm_output, reactionPrefixes):
    """
    yield reaction_added and reaction_removed events beginning with one of the prefix in reactionPrefixes
    """
    output_list = slack_rtm_output
    if output_list is not None and len(output_list) > 0:
        for output in output_list:
            if output is not None and 'type' in output:
                if 'reaction_added' in output['type'] or 'reaction_removed' in output['type']:
                    reactionName = output['reaction']
                    for prefix in reactionPrefixes:
                        if reactionName.startswith(prefix):
                            yield prefix, output
    yield None, None

def getUserMessageReactions(client, user):
    """
    yield all messages to which user reacted
    """
    reactionList = client.api_call('reactions.list',user=user)
    if reactionList['ok']:
        paging = reactionList['paging']
        for reaction in reactionList['items']:
            if reaction['type'] == 'message':
                yield reaction['message']

def getPrivateChannelName(client, channelId):
    """
    return the name of a private channel
    """
    channelObject = client.api_call('groups.info', channel=channelId)
    if channelObject['ok']:
        return channelObject['group']['name']
    return 'ChannelUnknown'

def getChannelName(client, channelId):
    """
    return the name of a channel
    """
    channelObject = client.api_call('channels.info', channel=channelId)
    if channelObject['ok']:
        return channelObject['channel']['name']
    return 'ChannelUnknown'

def getUserName(client, userId):
    """
    return the name of a user (concatenation of username and realname)
    """
    userObject = client.api_call("users.info", user=userId)
    if userObject['ok']:
        realName = userObject['user']['profile']['real_name']
        name = userObject['user']['name']
        return '{} ({})'.format(realName, name) 
    return 'UserUnknown'
