import sqlite3
import os
import contextlib
from datetime import datetime
from typing import List, Optional, Iterator
from .models import Video, Channel

class VideoStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with self._connection() as conn:
            # Table: channels
            conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    name TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            # Table: videos
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    url TEXT NOT NULL,
                    viewed INTEGER DEFAULT 0,
                    started_at TEXT,
                    channel_id INTEGER,
                    platform TEXT,
                    video_id TEXT,
                    created_at TEXT,
                    FOREIGN KEY(channel_id) REFERENCES channels(id)
                )
            """)

            # Ensure UNIQUE constraint on url (watch_url)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_videos_url ON videos(url)")

    @contextlib.contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._connection() as conn:
            return conn.execute(query, params).fetchall()

    def _fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self._connection() as conn:
            return conn.execute(query, params).fetchone()

    def _run(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._connection() as conn:
            return conn.execute(query, params)

    def _row_to_video(self, row: sqlite3.Row) -> Video:
        # Construct Channel object from row (JOIN query results)
        channel_obj = Channel(
            id=row['channel_id'],
            platform=row['platform'],
            name=row['channel'],
            external_id=row['external_id'],
            created_at=datetime.fromisoformat(row['channel_created_at'])
        )
        return Video(
            id=row['id'],
            title=row['title'],
            channel=channel_obj,
            upload_date=datetime.fromisoformat(row['upload_date']),
            url=row['url'],
            viewed=bool(row['viewed']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            platform=row['platform'],
            channel_id=row['channel_id'],
            video_id=row['video_id'],
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        )

    def _row_to_channel(self, row: sqlite3.Row) -> Channel:
        return Channel(
            id=row['id'],
            platform=row['platform'],
            name=row['name'],
            external_id=row['external_id'],
            created_at=datetime.fromisoformat(row['created_at'])
        )

    @property
    def videos(self) -> List[Video]:
        # Compatibility property: returns newest 100 videos
        return self.get_new_videos(100)

    def save(self) -> None:
        # Compatibility: no-op since we use auto-commit in context manager
        pass

    def add_video(self, video: Video) -> int:
        cursor = self._run("""
            INSERT OR IGNORE INTO videos (id, title, channel, upload_date, url, viewed, started_at, channel_id, platform, video_id, created_at)
            VALUES (:id, :title, :channel, :upload_date, :url, :viewed, :started_at, :channel_id, :platform, :video_id, :created_at)
        """, video.to_dict())
        return cursor.rowcount

    def get_video_by_id(self, video_id: str) -> Optional[Video]:
        row = self._fetch_one("""
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.id = ?
        """, (video_id,))
        return self._row_to_video(row) if row else None

    def update_video(self, video: Video) -> None:
        self._run("""
            UPDATE videos
            SET title = :title, channel = :channel, upload_date = :upload_date, url = :url, viewed = :viewed,
                started_at = :started_at, channel_id = :channel_id, platform = :platform, video_id = :video_id, created_at = :created_at
            WHERE id = :id
        """, video.to_dict())

    def save_channel(self, platform: str, name: str, external_id: str) -> int:
        cursor = self._run("""
            INSERT INTO channels (platform, name, external_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (platform, name, external_id, datetime.now().isoformat()))
        return cursor.lastrowid

    def get_channels(self) -> List[Channel]:
        rows = self._fetch_all("SELECT * FROM channels")
        return [self._row_to_channel(row) for row in rows]

    def get_channel_by_external_id(self, platform: str, external_id: str) -> Optional[Channel]:
        row = self._fetch_one("SELECT * FROM channels WHERE platform = ? AND external_id = ?", (platform, external_id))
        return self._row_to_channel(row) if row else None

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        row = self._fetch_one("SELECT * FROM channels WHERE id = ?", (channel_id,))
        return self._row_to_channel(row) if row else None

    def delete_channel(self, channel_id: int) -> None:
        self._run("DELETE FROM videos WHERE channel_id = ?", (channel_id,))
        self._run("DELETE FROM channels WHERE id = ?", (channel_id,))

    def get_latest_video_date(self, channel_id: int) -> Optional[datetime]:
        row = self._fetch_one("SELECT MAX(upload_date) AS val FROM videos WHERE channel_id = ?", (channel_id,))
        if row and row['val']:
            return datetime.fromisoformat(row['val'])
        return None

    def get_oldest_video_date(self, channel_id: int) -> Optional[datetime]:
        row = self._fetch_one("SELECT MIN(upload_date) AS val FROM videos WHERE channel_id = ?", (channel_id,))
        if row and row['val']:
            return datetime.fromisoformat(row['val'])
        return None

    def get_new_videos(self, limit: int = 100) -> List[Video]:
        rows = self._fetch_all("""
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            ORDER BY v.upload_date DESC LIMIT ?
        """, (limit,))
        return [self._row_to_video(row) for row in rows]

    def _fetch_all_videos_by_channel(self, channel_id: int, limit: int = 100) -> List[Video]:
        rows = self._fetch_all("""
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.channel_id = ?
            ORDER BY v.upload_date DESC LIMIT ?
        """, (channel_id, limit))
        return [self._row_to_video(row) for row in rows]

    def get_random_videos(self, limit: int = 100) -> List[Video]:
        rows = self._fetch_all("""
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            ORDER BY RANDOM() LIMIT ?
        """, (limit,))
        return [self._row_to_video(row) for row in rows]

    def get_related_videos(self, target_id: str, limit: int = 100) -> List[Video]:
        target = self.get_video_by_id(target_id)
        if not target:
            return []

        rows = self._fetch_all("""
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.channel_id = ? AND v.id != ?
            ORDER BY v.viewed ASC, ABS(strftime('%s', v.upload_date) - strftime('%s', ?)) ASC
            LIMIT ?
        """, (target.channel_id, target.id, target.upload_date.isoformat(), limit))
        return [self._row_to_video(row) for row in rows]

    def _find_related_unviewed(self, current_video: Optional[Video], exclude_ids: List[str]) -> Optional[Video]:
        if not current_video:
            return None

        query = """
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.channel_id = ? AND v.viewed = 0
        """
        params = [current_video.channel_id]
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND v.id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY ABS(strftime('%s', v.upload_date) - strftime('%s', ?)) ASC LIMIT 1"
        params.append(current_video.upload_date.isoformat())

        row = self._fetch_one(query, tuple(params))
        return self._row_to_video(row) if row else None

    def _find_newest_unviewed(self, exclude_ids: List[str]) -> Optional[Video]:
        query = """
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.viewed = 0
        """
        params = []
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND v.id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY v.upload_date DESC LIMIT 1"
        row = self._fetch_one(query, tuple(params))
        return self._row_to_video(row) if row else None

    def _find_related_viewed(self, current_video: Optional[Video], exclude_ids: List[str]) -> Optional[Video]:
        if not current_video:
            return None

        query = """
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
            WHERE v.channel_id = ? AND v.viewed = 1
        """
        params = [current_video.channel_id]
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND v.id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY ABS(strftime('%s', v.upload_date) - strftime('%s', ?)) ASC LIMIT 1"
        params.append(current_video.upload_date.isoformat())

        row = self._fetch_one(query, tuple(params))
        return self._row_to_video(row) if row else None

    def _find_stable_fallback(self, exclude_ids: List[str]) -> Optional[Video]:
        query = """
            SELECT v.*, c.external_id, c.created_at as channel_created_at
            FROM videos v
            JOIN channels c ON v.channel_id = c.id
        """
        params = []
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"WHERE v.id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY v.title ASC, v.id ASC LIMIT 1"
        row = self._fetch_one(query, tuple(params))
        return self._row_to_video(row) if row else None

    def select_next_video(self, current_id: Optional[str] = None, last_id: Optional[str] = None) -> Optional[Video]:
        exclude_ids = [i for i in [current_id, last_id] if i]
        current_video = self.get_video_by_id(current_id) if current_id else None

        video = self._find_related_unviewed(current_video, exclude_ids)
        if video: return video

        video = self._find_newest_unviewed(exclude_ids)
        if video: return video

        video = self._find_related_viewed(current_video, exclude_ids)
        if video: return video

        return self._find_stable_fallback(exclude_ids)
