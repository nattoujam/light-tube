import sqlite3
import os
from datetime import datetime
from typing import List, Optional
from .models import Video

class VideoStorage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    upload_date TEXT NOT NULL,
                    url TEXT NOT NULL,
                    viewed INTEGER DEFAULT 0,
                    started_at TEXT
                )
            """)
            conn.commit()

    def _row_to_video(self, row: sqlite3.Row) -> Video:
        return Video(
            id=row['id'],
            title=row['title'],
            channel=row['channel'],
            upload_date=datetime.fromisoformat(row['upload_date']),
            url=row['url'],
            viewed=bool(row['viewed']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None
        )

    @property
    def videos(self) -> List[Video]:
        # Compatibility property: returns newest 100 videos
        return self.get_new_videos(100)

    def save(self) -> None:
        # Compatibility: no-op since we use auto-commit in context manager
        pass

    def add_video(self, video: Video) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO videos (id, title, channel, upload_date, url, viewed, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                video.id,
                video.title,
                video.channel,
                video.upload_date.isoformat(),
                video.url,
                1 if video.viewed else 0,
                video.started_at.isoformat() if video.started_at else None
            ))
            conn.commit()

    def get_video_by_id(self, video_id: str) -> Optional[Video]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = cursor.fetchone()
            return self._row_to_video(row) if row else None

    def update_video(self, video: Video) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE videos
                SET title = ?, channel = ?, upload_date = ?, url = ?, viewed = ?, started_at = ?
                WHERE id = ?
            """, (
                video.title,
                video.channel,
                video.upload_date.isoformat(),
                video.url,
                1 if video.viewed else 0,
                video.started_at.isoformat() if video.started_at else None,
                video.id
            ))
            conn.commit()

    def get_new_videos(self, limit: int = 100) -> List[Video]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM videos ORDER BY upload_date DESC LIMIT ?", (limit,))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def get_random_videos(self, limit: int = 100) -> List[Video]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM videos ORDER BY RANDOM() LIMIT ?", (limit,))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def get_related_videos(self, target_id: str, limit: int = 100) -> List[Video]:
        target = self.get_video_by_id(target_id)
        if not target:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Related logic: Same channel, unviewed first, then by date proximity
            # We use ABS(strftime('%s', upload_date) - strftime('%s', ?)) for date proximity
            cursor = conn.execute("""
                SELECT * FROM videos
                WHERE channel = ? AND id != ?
                ORDER BY viewed ASC, ABS(strftime('%s', upload_date) - strftime('%s', ?)) ASC
                LIMIT ?
            """, (target.channel, target.id, target.upload_date.isoformat(), limit))
            return [self._row_to_video(row) for row in cursor.fetchall()]

    def select_next_video(self, current_id: Optional[str] = None, last_id: Optional[str] = None) -> Optional[Video]:
        exclude_ids = [i for i in [current_id, last_id] if i]

        current_video = self.get_video_by_id(current_id) if current_id else None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Rule 1: Related Unviewed
            if current_video:
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
                if row:
                    return self._row_to_video(row)

            # Rule 3: New tab unviewed (all unviewed, newest first)
            query = "SELECT * FROM videos WHERE viewed = 0 "
            params = []
            if exclude_ids:
                placeholders = ','.join(['?'] * len(exclude_ids))
                query += f"AND id NOT IN ({placeholders}) "
                params.extend(exclude_ids)

            query += "ORDER BY upload_date DESC LIMIT 1"
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if row:
                return self._row_to_video(row)

            # Rule 4: Related Viewed
            if current_video:
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
                if row:
                    return self._row_to_video(row)

            # Rule 5: Stable Fallback
            query = "SELECT * FROM videos "
            params = []
            if exclude_ids:
                placeholders = ','.join(['?'] * len(exclude_ids))
                query += f"WHERE id NOT IN ({placeholders}) "
                params.extend(exclude_ids)

            query += "ORDER BY title ASC, id ASC LIMIT 1"
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            if row:
                return self._row_to_video(row)

        return None
