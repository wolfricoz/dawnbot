from abc import ABC, abstractmethod

from sqlalchemy import select

import components.database as db


class transaction(ABC):
    @staticmethod
    @abstractmethod
    def get_user(session, id):
        session.close()
        user = session.scalars(select(db.Users).where(db.Users.uid == id)).first()
        if user is None:
            user = db.Users(uid=id)
            session.add(user)
            session.commit()
        return user

    @staticmethod
    @abstractmethod
    def get_roles(session, guild):
        query = session.scalars(select(db.Levels).where(db.Levels.guildid == guild.id)).all()
        temp_roles = [x.role_id for x in query]
        roles = []
        for r in temp_roles:
            roles.append(guild.get_role(r))
        return roles

    @staticmethod
    @abstractmethod
    def get_highest_role(session, guild, user):
        query = session.scalars(select(db.Levels).where(db.Levels.guildid == guild.id)).all()
        possible_ranks = {}
        for q in query:
            if user.xp >= q.xp_required:
                possible_ranks[q.role_id] = q.xp_required
        role = [x for x in possible_ranks if possible_ranks[x] == max(possible_ranks.values())]
        if len(role) > 0:
            return role[0]

    @staticmethod
    @abstractmethod
    def get_lowest_role(session, guild, user):
        query = session.scalars(select(db.Levels).where(db.Levels.guildid == guild.id)).all()
        possible_ranks = {}
        for q in query:
            if user.xp >= q.xp_required:
                continue
            possible_ranks[q.role_id] = q.xp_required

        role = [x for x in possible_ranks if possible_ranks[x] == min(possible_ranks.values())]

        role.append(query[-1].role_id)
        rankinfo = possible_ranks.get(role[0])
        return role[0], rankinfo
