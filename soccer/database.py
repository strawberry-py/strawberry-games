from __future__ import annotations

from typing import List, Optional

from sqlalchemy import BigInteger, Column

from pie.database import database, session


class SoccerChannel(database.base):
    __tablename__ = "games_soccer_channel"
    guild_id = Column(BigInteger, primary_key=True)
    channel_id = Column(BigInteger, primary_key=True)

    @staticmethod
    def add(guild_id: int, channel_id: int) -> SoccerChannel:
        channel = SoccerChannel(guild_id=guild_id, channel_id=channel_id)

        session.merge(channel)
        session.commit()

        return channel

    @staticmethod
    def exists(guild_id: int, channel_id: int) -> bool:
        query = (
            session.query(SoccerChannel)
            .filter_by(guild_id=guild_id, channel_id=channel_id)
            .one_or_none()
        )

        return query is not None

    @staticmethod
    def get(guild_id: int, channel_id: int) -> Optional[SoccerChannel]:
        query = (
            session.query(SoccerChannel)
            .filter_by(guild_id=guild_id, channel_id=channel_id)
            .one_or_none()
        )

        return query

    @staticmethod
    def get_all(guild_id) -> List[SoccerChannel]:
        query = session.query(SoccerChannel).filter_by(guild_id=guild_id).all()

        return query

    def delete(self):
        session.delete(self)
        session.commit()


class SoccerIgnored(database.base):
    __tablename__ = "games_soccer_ignored"
    guild_id = Column(BigInteger, primary_key=True)
    thread_id = Column(BigInteger, primary_key=True)

    @staticmethod
    def add(guild_id: int, thread_id: int) -> SoccerIgnored:
        channel = SoccerIgnored(guild_id=guild_id, thread_id=thread_id)

        session.merge(channel)
        session.commit()

        return channel

    @staticmethod
    def exists(guild_id: int, thread_id: int) -> bool:
        query = (
            session.query(SoccerIgnored)
            .filter_by(guild_id=guild_id, thread_id=thread_id)
            .one_or_none()
        )

        return query is not None

    @staticmethod
    def get(guild_id: int, thread_id: int) -> Optional[SoccerIgnored]:
        query = (
            session.query(SoccerIgnored)
            .filter_by(guild_id=guild_id, thread_id=thread_id)
            .one_or_none()
        )

        return query

    @staticmethod
    def get_all(guild_id) -> List[SoccerIgnored]:
        query = session.query(SoccerIgnored).filter_by(guild_id=guild_id).all()

        return query

    def delete(self):
        session.delete(self)
        session.commit()
