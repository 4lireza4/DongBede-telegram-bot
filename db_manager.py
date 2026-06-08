from peewee import SqliteDatabase, Model, IntegerField, CharField, ForeignKeyField, BooleanField, DateTimeField
from datetime import datetime
import config

db = SqliteDatabase(config.DB_NAME, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    user_id = IntegerField(primary_key=True)
    username = CharField(null=True)
    first_name = CharField(null=True)


class Transaction(BaseModel):
    creditor = ForeignKeyField(User, backref='credits')
    debtor = ForeignKeyField(User, backref='debts')
    amount = IntegerField()
    description = CharField(null=True)
    is_settled = BooleanField(default=False)
    created_at = DateTimeField(default=datetime.now)


def init_db():
    db.connect()
    db.create_tables([User, Transaction])
    db.close()


def upsert_user(user_id: int, username: str, first_name: str):
    User.insert(
        user_id=user_id,
        username=username,
        first_name=first_name
    ).on_conflict_replace().execute()


def add_transaction(creditor_id: int, debtor_id: int, amount: int, description: str):
    Transaction.create(
        creditor=creditor_id,
        debtor=debtor_id,
        amount=amount,
        description=description
    )


def get_user_balances(user_id: int) -> dict:
    transactions = Transaction.select().where(
        ((Transaction.creditor == user_id) | (Transaction.debtor == user_id)) &
        (Transaction.is_settled == False)
    )

    balances = {}

    for txn in transactions:
        if txn.creditor_id == user_id:
            target_id = txn.debtor_id
            target_name = txn.debtor.first_name
            amount = txn.amount
        else:
            target_id = txn.creditor_id
            target_name = txn.creditor.first_name
            amount = -txn.amount

        if target_id not in balances:
            balances[target_id] = {'name': target_name, 'net_amount': 0}

        balances[target_id]['net_amount'] += amount

    return {k: v for k, v in balances.items() if v['net_amount'] != 0}


def get_transaction_history(user_id: int, target_user_id: int, limit: int = 10):
    transactions = Transaction.select().where(
        ((Transaction.creditor == user_id) & (Transaction.debtor == target_user_id)) |
        ((Transaction.creditor == target_user_id) & (Transaction.debtor == user_id))
    ).order_by(Transaction.created_at.desc()).limit(limit)

    return transactions


def get_recent_contacts(user_id: int) -> dict:
    transactions = Transaction.select().where(
        (Transaction.creditor == user_id) | (Transaction.debtor == user_id)
    ).order_by(Transaction.created_at.desc())

    contacts = {}
    for txn in transactions:
        if txn.creditor_id == user_id:
            contacts[txn.debtor_id] = txn.debtor.first_name
        else:
            contacts[txn.creditor_id] = txn.creditor.first_name

        if len(contacts) >= 8:
            break

    return contacts


def get_user_info(user_id: int):
    return User.get_or_none(User.user_id == user_id)


def settle_transaction(txn_id: int):
    txn = Transaction.get_or_none(Transaction.id == txn_id)
    if txn:
        txn.is_settled = True
        txn.save()
    return txn
    return None
