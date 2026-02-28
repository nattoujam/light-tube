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

    def _row_to_video(self, row: sqlite3.Row) -> Video:
        return Video(
            id=row['id'],
            title=row['title'],
            channel=row['channel'],
            upload_date=datetime.fromisoformat(row['upload_date']),
            url=row['url'],
            viewed=bool(row['viewed']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            platform=row['platform'] if 'platform' in row.keys() else None,
            channel_id=row['channel_id'] if 'channel_id' in row.keys() else None,
            video_id=row['video_id'] if 'video_id' in row.keys() else None,
            created_at=datetime.fromisoformat(row['created_at']) if 'created_at' in row.keys() and row['created_at'] else None
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
        with self._connection() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO videos (id, title, channel, upload_date, url, viewed, started_at, channel_id, platform, video_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video.id,
                video.title,
                video.channel,
                video.upload_date.isoformat(),
                video.url,
                1 if video.viewed else 0,
                video.started_at.isoformat() if video.started_at else None,
                video.channel_id,
                video.platform,
                video.video_id,
                video.created_at.isoformat() if video.created_at else None
            ))
            return cursor.rowcount

    def get_video_by_id(self, video_id: str) -> Optional[Video]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = cursor.fetchone()
            return self._row_to_video(row) if row else None

    def update_video(self, video: Video) -> None:
        with self._connection() as conn:
            conn.execute("""
                UPDATE videos
                SET title = ?, channel = ?, upload_date = ?, url = ?, viewed = ?, started_at = ?, channel_id = ?, platform = ?, video_id = ?, created_at = ?
                WHERE id = ?
            """, (
                video.title,
                video.channel,
                video.upload_date.isoformat(),
                video.url,
                1 if video.viewed else 0,
                video.started_at.isoformat() if video.started_at else None,
                video.channel_id,
                video.platform,
                video.video_id,
                video.created_at.isoformat() if video.created_at else None,
                video.id
            ))

    def save_channel(self, platform: str, name: str, external_id: str) -> int:
        with self._connection() as conn:
            cursor = conn.execute("""
                INSERT INTO channels (platform, name, external_id, created_at)
                VALUES (?, ?, ?, ?)
            """, (platform, name, external_id, datetime.now().isoformat()))
            return cursor.lastrowid

    def get_channels(self) -> List[Channel]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM channels")
            return [self._row_to_channel(row) for row in cursor.fetchall()]

    def get_channel_by_external_id(self, platform: str, external_id: str) -> Optional[Channel]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM channels WHERE platform = ? AND external_id = ?", (platform, external_id))
            row = cursor.fetchone()
            return self._row_to_channel(row) if row else None

    def get_channel_by_id(self, channel_id: int) -> Optional[Channel]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
            row = cursor.fetchone()
            return self._row_to_channel(row) if row else None

    def get_new_videos(self, limit: int = 100) -> List[Video]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM videos ORDER BY upload_date DESC LIMIT ?", (limit,))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def get_random_videos(self, limit: int = 100) -> List[Video]:
        with self._connection() as conn:
            cursor = conn.execute("SELECT * FROM videos ORDER BY RANDOM() LIMIT ?", (limit,))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def get_related_videos(self, target_id: str, limit: int = 100) -> List[Video]:
        target = self.get_video_by_id(target_id)
        if not target:
            return []

        with self._connection() as conn:
            # Related logic: Same channel, unviewed first, then by date proximity
            # We use ABS(strftime('%s', upload_date) - strftime('%s', ?)) for date proximity
            cursor = conn.execute("""
                SELECT * FROM videos
                WHERE channel = ? AND id != ?
                ORDER BY viewed ASC, ABS(strftime('%s', upload_date) - strftime('%s', ?)) ASC
                LIMIT ?
            """, (target.channel, target.id, target.upload_date.isoformat(), limit))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def _find_related_unviewed(self, conn: sqlite3.Connection, current_video: Optional[Video], exclude_ids: List[str]) -> Optional[Video]:
        if not current_video:
            return None

        query = "SELECT * FROM videos WHERE channel = ? AND viewed = 0 "
        params = [current_video.channel]
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY ABS(strftime('%s', upload_date) - strftime('%s', ?)) ASC LIMIT 1"
        params.append(current_video.upload_date.isoformat())

        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return self._row_to_video(row) if row else None

    def _find_newest_unviewed(self, conn: sqlite3.Connection, exclude_ids: List[str]) -> Optional[Video]:
        query = "SELECT * FROM videos WHERE viewed = 0 "
        params = []
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY upload_date DESC LIMIT 1"
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return self._row_to_video(row) if row else None

    def _find_related_viewed(self, conn: sqlite3.Connection, current_video: Optional[Video], exclude_ids: List[str]) -> Optional[Video]:
        if not current_video:
            return None

        query = "SELECT * FROM videos WHERE channel = ? AND viewed = 1 "
        params = [current_video.channel]
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"AND id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY ABS(strftime('%s', upload_date) - strftime('%s', ?)) ASC LIMIT 1"
        params.append(current_video.upload_date.isoformat())

        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return self._row_to_video(row) if row else None

    def _find_stable_fallback(self, conn: sqlite3.Connection, exclude_ids: List[str]) -> Optional[Video]:
        query = "SELECT * FROM videos "
        params = []
        if exclude_ids:
            placeholders = ','.join(['?'] * len(exclude_ids))
            query += f"WHERE id NOT IN ({placeholders}) "
            params.extend(exclude_ids)

        query += "ORDER BY title ASC, id ASC LIMIT 1"
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return self._row_to_video(row) if row else None

    def select_next_video(self, current_id: Optional[str] = None, last_id: Optional[str] = None) -> Optional[Video]:
        exclude_ids = [i for i in [current_id, last_id] if i]
        current_video = self.get_video_by_id(current_id) if current_id else None

        with self._connection() as conn:
            # Rule 1: Related Unviewed
            video = self._find_related_unviewed(conn, current_video, exclude_ids)
            if video:
                return video

            # Rule 3: New tab unviewed (all unviewed, newest first)
            video = self._find_newest_unviewed(conn, exclude_ids)
            if video:
                return video

            # Rule 4: Related Viewed
            video = self._find_related_viewed(conn, current_video, exclude_ids)
            if video:
                return video

            # Rule 5: Stable Fallback
            return self._find_stable_fallback(conn, exclude_ids)
