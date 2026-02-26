import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.platform.youtube import YouTube
from core.platform.niconico import Niconico
from core.repository import Repository
from app.models import Video

def test_platform_a_fetch_videos():
    api_key = "test_key"
    platform = YouTube(api_key)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "Title 1",
                    "publishedAt": "2023-01-01T00:00:00Z"
                }
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        videos = platform.fetch_videos("channel1")
        assert len(videos) == 1
        assert videos[0].video_id == "vid1"
        assert videos[0].title == "Title 1"
        assert videos[0].watch_url == "https://www.youtube.com/watch?v=vid1"

def test_repository_save_remote_videos():
    mock_storage = MagicMock()
    repo = Repository(mock_storage)

    from core.platform.base import RemoteVideo
    rvs = [
        RemoteVideo(video_id="vid1", title="Title 1", published_at=datetime(2023, 1, 1), watch_url="url1")
    ]

    repo.save_remote_videos(1, "youtube", "Channel A", rvs)

    assert mock_storage.add_video.called
    video = mock_storage.add_video.call_args[0][0]
    assert video.video_id == "vid1"
    assert video.platform == "youtube"
    assert video.channel_id == 1
