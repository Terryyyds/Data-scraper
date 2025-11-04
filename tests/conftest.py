"""Pytest configuration and fixtures."""
import pytest
import json
from pathlib import Path


@pytest.fixture
def sample_post_data():
    """Sample post data from API response."""
    return {
        "id": 970141,
        "timeStr": "今天 14:51",
        "time_str": "今天 14:51",
        "timeDate": "Nov 3, 2025 2:51:46 PM",
        "hits": 3,
        "title": "",
        "multitextType": 1,
        "topicId": 0,
        "replyCounter": 1,
        "extContent": "",
        "content": "真正厉害的人，从不分享过去的痛苦。",
        "uid": 15427050,
        "name": "赤橙黄绿青蓝紫！",
        "gender": 2,
        "askTag": "",
        "zanCount": 1,
        "avatar": "http://ydl-userprivacy.ydl.com/2024_06_01_92901610000PVPVSPWVPSXRY.png",
        "header": "http://ydl-userprivacy.ydl.com/2024_06_01_92901610000PVPVSPWVPSXRY.png",
        "commentsCount": 1,
        "topicTitle": "",
        "isZan": 2,
        "visitCount": 3,
        "from": "来自Unknown客户端",
        "smallAttach": [],
        "bigAttach": [],
        "utype": 2,
        "isAd": 0,
        "is_ad": 0,
        "url": "",
        "adImg": "",
        "focId": 0,
        "isFocused": 2,
        "share": None,
        "isSelf": 0,
        "comments": [
            {
                "name": "暖暖",
                "content": "你这句话像一片轻轻飘落的羽毛，落在了我心里最柔软的地方呢。",
                "toName": "",
                "to_name": "",
                "userHead": "https://pic.ydlcdn.com/35f2M8Xi64.png",
                "answerCreateTime": "今天 14:51",
                "time_str": "今天 14:51",
                "toContent": "",
                "to_content": "",
                "isZan": 2,
                "id": 4831707,
                "uid": 32104968,
                "askId": 970141,
                "zan": 0,
                "gender": 1,
                "userType": 1,
                "user_type": 1,
                "doctorId": 0,
                "doctor_id": 0,
                "isOpenListen": 0,
                "isAvailable": 0,
                "listenLinkUrl": "https://h2.yidianling.com/experts/0?id=null&toConfide=1",
                "ip": "",
                "ipProvince": ""
            }
        ],
        "ext": None,
        "isAssistantGuide": 0,
        "assistantGuideImg": "",
        "isAssistantGuideExit": 0,
        "ip": ""
    }


@pytest.fixture
def sample_post_with_reply():
    """Sample post with nested replies."""
    return {
        "id": 970135,
        "timeStr": "今天 05:43",
        "time_str": "今天 05:43",
        "hits": 22,
        "content": "我妈现在总和我说我爸能力不行了。",
        "uid": 0,
        "name": "匿名",
        "gender": 1,
        "zanCount": 1,
        "avatar": "http://img.ydlcdn.com/v2/images/avatar_default.png",
        "commentsCount": 3,
        "topicTitle": "我的情绪日记",
        "visitCount": 22,
        "from": "来自Unknown客户端",
        "smallAttach": [],
        "bigAttach": [],
        "comments": [
            {
                "name": "暖暖",
                "content": "听起来你心里像揣了好多团乱麻",
                "toName": "豁达的瑞灵",
                "to_name": "豁达的瑞灵",
                "userHead": "https://pic.ydlcdn.com/35f2M8Xi64.png",
                "answerCreateTime": "今天 05:43",
                "time_str": "今天 05:43",
                "toContent": "我先是和她一起批评我爸",
                "to_content": "我先是和她一起批评我爸",
                "isZan": 2,
                "id": 4831691,
                "uid": 32104968,
                "zan": 0,
                "gender": 1,
                "userType": 1
            },
            {
                "name": "",
                "content": "我先是和她一起批评我爸",
                "toName": "暖暖",
                "to_name": "暖暖",
                "userHead": "",
                "answerCreateTime": "今天 05:48",
                "id": 4831692,
                "uid": 0,
                "zan": 0,
                "gender": 1,
                "userType": 1
            }
        ]
    }


@pytest.fixture
def sample_anonymous_post():
    """Sample anonymous post."""
    return {
        "id": 970140,
        "timeStr": "今天 14:32",
        "content": "每晚下班后 看见天上的月球 心里都在想 希望明天醒来会有好消息",
        "uid": 0,
        "name": "匿名",
        "gender": 1,
        "zanCount": 1,
        "avatar": "http://img.ydlcdn.com/v2/images/avatar_default.png",
        "commentsCount": 1,
        "visitCount": 4,
        "hits": 4,
        "from": "来自Mac OS X (iPhone)客户端",
        "smallAttach": [],
        "bigAttach": [],
        "comments": []
    }


@pytest.fixture
def sample_empty_page():
    """Sample empty page response."""
    return {
        "code": "200",
        "data": {
            "data": [],
            "extData": []
        },
        "msg": "成功"
    }

