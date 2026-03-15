import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from core.platform.youtube import YouTube
from core.repository import Repository
from app.models import Video, Channel
from core.platform.base import RemoteVideo

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
    mock_storage.add_video.return_value = 1
    repo = Repository(mock_storage)

    channel = Channel(id=1, platform="youtube", name="Channel A", external_id="ext1", created_at=datetime.now())

    rvs = [
        RemoteVideo(video_id="vid1", title="Title 1", published_at=datetime(2023, 1, 1), watch_url="url1")
    ]

    added = repo.save_remote_videos(channel, rvs)

    assert added == 1
    assert mock_storage.add_video.called
    video = mock_storage.add_video.call_args[0][0]
    assert video.video_id == "vid1"

def test_repository_sync_channel():
    mock_storage = MagicMock()
    mock_fetcher = MagicMock()
    repo = Repository(mock_storage, video_fetcher=mock_fetcher)

    channel = Channel(id=1, platform="youtube", name="Channel A", external_id="ext1", created_at=datetime.now())
    rvs = [RemoteVideo(video_id="vid1", title="Title 1", published_at=datetime(2023, 1, 1), watch_url="url1")]
    mock_fetcher.fetch_recent.return_value = rvs
    mock_storage.add_video.return_value = 1

    added = repo.sync_channel(channel, limit=10)

    assert added == 1
    mock_fetcher.fetch_recent.assert_called_once_with("youtube", "ext1", limit=10)

def test_repository_resolve_and_save_channel():
    mock_storage = MagicMock()
    mock_resolver = MagicMock()
    mock_fetcher = MagicMock()
    repo = Repository(mock_storage, video_fetcher=mock_fetcher, channel_resolver=mock_resolver)

    mock_resolver.resolve.return_value = "ext_id"
    mock_storage.save_channel.return_value = 1
    mock_fetcher.fetch_recent.return_value = []

    channel = repo.resolve_and_save_channel("youtube", "Channel Name", sync=True)

    assert channel.id == 1
    assert channel.external_id == "ext_id"
    mock_resolver.resolve.assert_called_once_with("youtube", "Channel Name")
    mock_storage.save_channel.assert_called_once_with("youtube", "Channel Name", "ext_id")
    mock_fetcher.fetch_recent.assert_called_once()
