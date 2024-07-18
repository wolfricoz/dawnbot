import json
import os
from abc import ABC, abstractmethod

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError, DBAPIError
from sqlalchemy.orm import Session

import components.database as db

session = Session(bind=db.engine)

class CommitError(Exception):
    """the commit failed."""

    def __init__(self, message="Commiting the data to the database failed and has been rolled back; please try again."):
        self.message = message
        super().__init__(self.message)


class TransactionController(ABC):

    @staticmethod
    @abstractmethod
    def commit(session):
        """

        :param session:
        """
        try:
            session.commit()
        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            raise CommitError()
        except DBAPIError as e:
            if e.connection_invalidated:
                db.engine.connect()
        finally:
            session.close()

    @staticmethod
    @abstractmethod
    def execute(session, query):
        """

        :param session:
        """
        try:
            session.execute(query)
        except SQLAlchemyError as e:
            print(e)
            session.rollback()
            raise CommitError()
        except DBAPIError as e:
            if e.connection_invalidated:
                db.engine.connect()
        finally:
            session.close()

    @staticmethod
    @abstractmethod
    def get_user(id, guildid):
        """

        :param id:
        :return:
        """
        session.close()
        user = session.scalar(select(db.Users).where(db.Users.uid == id, db.Users.guildid == guildid))
        if user is None:
            return TransactionController.add_user(id, guildid)
        return user

    @staticmethod
    @abstractmethod
    def add_user(id, guildid):
        """

        :param id:
        :return:
        """
        user = db.Users(uid=id, guildid=guildid)
        session.add(user)
        TransactionController.commit(session)
        return user

    @staticmethod
    @abstractmethod
    def get_roles(guild):
        """

        :param guild:
        :return:
        """
        query = session.scalars(select(db.Levels).where(db.Levels.guildid == guild.id)).all()
        temp_roles = [x.role_id for x in query]
        roles = []
        for r in temp_roles:
            roles.append(guild.get_role(r))
        return roles

    @staticmethod
    @abstractmethod
    def get_highest_role(guild, user):
        user = TransactionController.get_user(user.id, guild.id)
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
    def get_lowest_role(guild, user):
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


class currencyTransactions(ABC):
    @staticmethod
    @abstractmethod
    def add_currency(userid, guildid, currency_gained):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(currency=db.Users.currency + currency_gained)
        )
        TransactionController.execute(session, stmt)
        TransactionController.commit(session)

    @staticmethod
    @abstractmethod
    def remove_currency(userid, guildid, currency):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(currency=db.Users.currency - currency)
        )
        TransactionController.execute(session, stmt)
        TransactionController.commit(session)

    @staticmethod
    @abstractmethod
    def set_currency(userid, guildid, currency):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(currency=currency)
        )
        TransactionController.execute(session, stmt)
        TransactionController.commit(session)

    @staticmethod
    @abstractmethod
    def get_currency(message):
        user = TransactionController.get_user(message.author.id, message.guild.id)
        return user.currency


class xpTransactions(ABC):
    @staticmethod
    @abstractmethod
    def add_xp(userid, guildid, gained_xp):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(xp=db.Users.xp + gained_xp, messages=db.Users.messages + 1)
        )
        session.execute(stmt)
        TransactionController.commit(session)

    @staticmethod
    @abstractmethod
    def remove_xp(userid, guildid, xp):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(xp=db.Users.xp - xp, messages=db.Users.messages + 1)
        )
        session.execute(stmt)
        TransactionController.commit(session)

    @staticmethod
    @abstractmethod
    def set_xp(userid, guildid, xp):
        stmt = (
            update(db.Users).
            where(db.Users.uid == userid).
            where(db.Users.guildid == guildid).
            values(xp=xp, messages=db.Users.messages + 1)
        )
        session.execute(stmt)
        TransactionController.commit(session)


class CombatSystem(ABC):
    session = Session(db.engine)
    armor = {}
    weapons = {}
    characters = {}

    def load_all(self):
        self.load_armor()
        self.load_weapons()
        self.load_characters()
        if os.path.exists("debug") is False:
            os.mkdir("debug")
        with open("debug/characters.json", "w") as f:
            json.dump(self.characters, f, indent=4)
        with open("debug/armor.json", "w") as f:
            json.dump(self.armor, f, indent=4)
        with open("debug/weapons.json", "w") as f:
            json.dump(self.weapons, f, indent=4)

    def load_armor(self):
        self.armor.clear()
        for x in self.session.scalars(select(db.Armors)).all():
            self.armor[x.name] = {}
            self.armor[x.name]["id"] = x.id
            self.armor[x.name]["hp"] = x.hp
            self.armor[x.name]["ac"] = x.ac
            self.armor[x.name]["hitchance"] = x.hitchance
            self.armor[x.name]["modifier"] = x.modifier
        return self.armor

    def load_weapons(self):
        self.weapons.clear()
        for x in self.session.scalars(select(db.Weapons)).all():
            self.weapons[x.name] = {}
            self.weapons[x.name]["dice"] = x.dice
            self.weapons[x.name]["modifier"] = x.modifier
            self.weapons[x.name]["hitmodifier"] = x.hitmodifier
        return self.weapons

    def load_characters(self):
        self.characters.clear()
        for x in self.session.scalars(select(db.Characters)).all():
            if x.uid not in self.characters:
                self.characters[x.uid] = {}
            self.characters[x.uid][x.name] = {}
            self.characters[x.uid][x.name]["prestige"] = x.prestige
            self.characters[x.uid][x.name]["strength"] = x.strength
            self.characters[x.uid][x.name]["perception"] = x.perception
            self.characters[x.uid][x.name]["endurance"] = x.endurance
            self.characters[x.uid][x.name]["charisma"] = x.charisma
            self.characters[x.uid][x.name]["intelligence"] = x.intelligence
            self.characters[x.uid][x.name]["agility"] = x.agility

            self.characters[x.uid][x.name]["armor"] = x.armor
        return self.characters

    def create_character(self, user, name, armor, strength, perception, endurance, charisma, intelligence, agility, prestige):
        armor = self.armor[armor]["id"]

        character = db.Characters(uid=user.id, name=name, armor=armor, strength=strength, perception=perception,
                                  endurance=endurance, charisma=charisma, intelligence=intelligence, agility=agility,
                                  prestige=prestige)
        self.session.add(character)
        TransactionController.commit(self.session)
        self.load_characters()
        return character

    def create_armor(self, name: str, hp, ac, hitchance, modifier) -> db.Armors:
        """

        :param name:
        :param hp:
        :param ac:
        :param hitchance:
        :param modifier:
        :return db.Armors:
        """
        armor = db.Armors(name=name.lower(), hp=hp, ac=ac, hitchance=hitchance, modifier=modifier.lower())
        self.session.add(armor)
        TransactionController.commit(self.session)
        self.load_armor()
        return armor

    def create_weapon(self, name: str, dice: str, modifier: str, hitmodifier: int) -> db.Weapons:
        """

        :param name:
        :param dice:
        :param modifier:
        :return db.Weapons:
        """
        weapon = db.Weapons(name=name.lower(), dice=dice.lower(), modifier=modifier.lower(), hitmodifier=hitmodifier)
        self.session.add(weapon)
        TransactionController.commit(self.session)
        self.load_weapons()
        return weapon

    def get_weapons(self):
        return self.weapons

    def get_characters(self):
        return self.characters

    def get_armor_by_id(self, id: int):
        for y, x in self.armor.items():
            if x["id"] == id:
                return self.armor[y]

    def remove_weapon(self, name: str) -> None:
        """

        :param name:
        :return None:
        """
        weapon = self.session.scalars(select(db.Weapons).where(db.Weapons.name == name)).first()
        self.session.delete(weapon)
        TransactionController.commit(self.session)
        self.load_weapons()
        return None

    def remove_armor(self, name: str) -> None:
        """

        :param name:
        :return None:
        """
        armor = self.session.scalars(select(db.Armors).where(db.Armors.name == name)).first()
        self.session.delete(armor)
        TransactionController.commit(self.session)
        self.load_armor()
        return None

    def remove_character(self, user, name: str) -> None:
        """

        :param user:
        :param name:
        :return None:
        """
        character = self.session.scalars(select(db.Characters).where(db.Characters.uid == user.id).where(db.Characters.name == name)).first()
        self.session.delete(character)
        TransactionController.commit(self.session)
        self.load_characters()
        return None

    def update_weapon(self, name: str, dice: str, modifier: str, hitmodifier: int) -> db.Weapons:
        """

        :param name:
        :param dice:
        :param modifier:
        :return db.Weapons:
        """
        weapon = self.session.scalars(select(db.Weapons).where(db.Weapons.name == name)).first()
        weapon.dice = dice
        weapon.modifier = modifier
        weapon.hitmodifier = hitmodifier
        TransactionController.commit(self.session)
        self.load_weapons()
        return weapon

    def update_armor(self, name: str, hp, ac, hitchance, modifier) -> db.Armors:
        """

        :param name:
        :param hp:
        :param ac:
        :param hitchance:
        :param modifier:
        :return db.Armors:
        """
        armor = self.session.scalars(select(db.Armors).where(db.Armors.name == name)).first()
        armor.hp = hp
        armor.ac = ac
        armor.hitchance = hitchance
        armor.modifier = modifier
        TransactionController.commit(self.session)
        self.load_armor()
        return armor

    def update_character(self, user, name, armor, strength, perception, endurance, charisma, intelligence, agility, prestige):
        """

        :param user:
        :param name:
        :param armor:
        :param strength:
        :param perception:
        :param endurance:
        :param charisma:
        :param intelligence:
        :param agility:
        :param prestige:
        :return None:
        """
        character = self.session.scalars(select(db.Characters).where(db.Characters.uid == user.id).where(db.Characters.name == name)).first()

        character.armor = self.armor[armor]["id"] if armor is not None else character.armor
        character.strength = strength if strength is not None else character.strength
        character.perception = perception if perception is not None else character.perception
        character.endurance = endurance if endurance is not None else character.endurance
        character.charisma = charisma if charisma is not None else character.charisma
        character.intelligence = intelligence if intelligence is not None else character.intelligence
        character.agility = agility if agility is not None else character.agility
        character.prestige = prestige if prestige is not None else character.prestige
        TransactionController.commit(self.session)
        self.load_characters()
        return None
