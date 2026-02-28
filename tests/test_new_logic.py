import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.platform.youtube import YouTube
from core.repository import Repository
from app.models import Video

@patch("requests.get")
def test_platform_a_fetch_videos(mock_get):
    api_key = "test_key"
    platform = YouTube(api_key)

    # Mock for _get_uploads_playlist_id
    mock_channel_response = MagicMock()
    mock_channel_response.json.return_value = {
        "items": [
            {
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": "UUXxxxx"
                    }
                }
            }
        ]
    }
    mock_channel_response.raise_for_status = MagicMock()

    # Mock for playlistItems
    mock_playlist_response = MagicMock()
    mock_playlist_response.json.return_value = {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid1"},
                    "title": "Title 1",
                    "publishedAt": "2023-01-01T00:00:00Z"
                }
            }
        ]
    }
    mock_playlist_response.raise_for_status = MagicMock()

    mock_get.side_effect = [mock_channel_response, mock_playlist_response]

    videos = platform.fetch_videos("channel1")
    assert len(videos) == 1
    assert videos[0].video_id == "vid1"
    assert videos[0].title == "Title 1"
    assert videos[0].watch_url == "https://www.youtube.com/watch?v=vid1"

def test_repository_save_remote_videos():
    mock_storage = MagicMock()
    # Mock return value for add_video (1 row inserted)
    mock_storage.add_video.return_value = 1
    repo = Repository(mock_storage)

    from core.platform.base import RemoteVideo
    rvs = [
        RemoteVideo(video_id="vid1", title="Title 1", published_at=datetime(2023, 1, 1), watch_url="url1")
    ]

    added = repo.save_remote_videos(1, "youtube", "Channel A", rvs)

    assert added == 1
    assert mock_storage.add_video.called
    video = mock_storage.add_video.call_args[0][0]
    assert video.video_id == "vid1"
    assert video.platform == "youtube"
    assert video.channel_id == 1
