from functools import reduce
import json
import requests

from utility.hash_utils import hash_block
from utility.verification import Verification
from block import Block
from transaction import Transaction
from wallet import Wallet

# The reward given to the miners (for creating a new block).
MINING_REWARD = 10

print(__name__)


class Blockchain:
    """The Blockchain class manages the chain of blocks as well as open
        transactions and the node on which it's running.

    Attributes:
        :chain: The list of blocks
        :open_transactions (private): The list of open transactions
        :hosting_node: The connected node (which runs the blockchain).
    """

    def __init__(self, public_key, node_id):
        # The starting block of blockchain.
        genesis_block = Block(0, "", [], 100, 0)
        # Initailizing our (empty) blockchain list.     Making it private.
        self.chain = [genesis_block]
        # Unhandeled transaction.                       Making it private.
        self.__open_transactions = list()
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

    @property
    def chain(self):
        return self.__chain[:]

    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transaction(self):
        """Returns a copy of the open transactions list."""
        return self.__open_transactions[:]

    def load_data(self):
        """Initialize blockchain by loading data from a file"""
        try:

            with open("blockchain-{}.txt".format(self.node_id), 'r') as file:
                file_content = file.readlines()

            # To remove the "\n" from the load, we are using range selector.
                blockchain = json.loads(file_content[0][:-1])
                updated_blockchain = list()

                for block in blockchain:
                    converted_tx = [Transaction(
                        tx['sender'],
                        tx['recipient'],
                        tx['signature'],
                        tx['amount']) for tx in block['transactions']]

                    updated_block = Block(
                        block['index'],
                        block['previous_hash'],
                        converted_tx,
                        block['proof'],
                        block['timestamp'])

                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transaction = json.loads(file_content[1][:-1])
                updated_transactions = list()

                for tx in open_transaction:
                    updated_transaction = Transaction(
                        tx['sender'],
                        tx['recipient'],
                        tx['signature'],
                        tx['amount'])
                    updated_transactions.append(updated_transaction)

                self.__open_transactions = updated_transactions
                peer_nodes = json.loads(file_content[2])
                self.__peer_nodes = set(peer_nodes)

        except (IOError, IndexError):
            print("Exception HANDLED")
            pass

        finally:
            print('Cleaned')

    def save_data(self):
        """Save blockchain + open transactions to a file."""
        try:
            with open("blockchain-{}.txt".format(self.node_id), 'w') as file:
                new_saveable_chain = [
                    block.__dict__ for block in
                    [
                        Block(new_block.index,
                              new_block.previous_hash,
                              [tx.__dict__ for tx in new_block.transactions],
                              new_block.proof,
                              new_block.timestamp)
                        for new_block in self.__chain]
                ]

                file.write(json.dumps(new_saveable_chain))
                file.write('\n')
                new_saveable_tx = [
                    block.__dict__ for block in self.__open_transactions]
                file.write(json.dumps(new_saveable_tx))
                file.write('\n')
                file.write(json.dumps(list(self.__peer_nodes)))

        except IOError:
            print("Saving Failed!!")

    def proof_of_work(self):
        """Generate a proof of work for the open transactions"""
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0

        while not Verification.valid_proof(
                self.__open_transactions,
                last_hash,
                proof
        ):
            proof += 1
        return proof

    def get_balance(self, sender=None):
        """Calculate and return balance of the participant.
        """
        if sender is None:
            if self.public_key is None:
                return None
            participant = self.public_key
        else:
            participant = sender

        tx_sender = [
            [
                tx.amount for tx in block.transactions
                if tx.sender == participant
            ]
            for block in self.__chain
        ]

        open_tx_sender = [
            tx.amount
            for tx in self.__open_transactions
            if tx.sender == participant
        ]
        tx_sender.append(open_tx_sender)
        print(tx_sender)

        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)

        tx_recipient = [
            [
                tx.amount for tx in block.transactions
                if tx.recipient == participant
            ]
            for block in self.__chain
        ]

        amount_recieved = reduce(
            lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
            if len(tx_amt) > 0 else tx_sum + 0,
            tx_recipient,
            0
        )
        # Returns total balance.
        return amount_recieved - amount_sent

    def get_last_blockchain_value(self):
        """Returns the last value of the current blockchain."""
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    def add_transaction(self,
                        recipient,
                        sender,
                        signature,
                        amount=1.0,
                        is_receiving=False):
        """Append new value as well as last value to blockchain.

        Arguments:
            :sender: The sender of the coin.
            :recipient: The recipient of the coin.
            :amount: The amount of coin sent with the transaction.
            :signature: The signature of the sender.
        """
        transaction = Transaction(sender, recipient, signature, amount)
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url,
                                                 json={
                                                     'sender': sender,
                                                     'recipient': recipient,
                                                     'amount': amount,
                                                     'signature': signature
                                                 })
                        if (response.status_code == 400 or
                                response.status_code == 500):
                            print('Transaction declined, needs to resolve')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def mine_block(self):
        """Create a new block and add open transactions to it."""
        if self.public_key is None:
            return None

        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()

        # Miners should be rewarded for there work.
        reward_transaction = Transaction(
            "MINING", self.public_key, '', MINING_REWARD)

        copied_transaction = self.__open_transactions[:]
        for tx in copied_transaction:
            if not Wallet.verify_transaction(tx):
                return None
        copied_transaction.append(reward_transaction)
        block = Block(len(self.__chain), hashed_block,
                      copied_transaction, proof)

        self.__chain.append(block)
        # Resets the open_transaction to an empty list.
        self.__open_transactions = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [
                tx.__dict__ for tx in converted_block['transactions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('BLock declined, needs to resolve')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_block(self, block):
        """Add a block which was received via broadcasting to the local
        blockchain."""
        transactions = [Transaction(
            tx['sender'],
            tx['recipient'],
            tx['signature'],
            tx['amount'])
            for tx in block['transactions']]

        proof_is_valid = Verification.valid_proof(
            transactions[:-1], block['previous_hash'], block['proof'])

        hashes_matched = hash_block(self.chain[-1]) == block['previous_hash']

        if not proof_is_valid or not hashes_matched:
            return False

        converted_block = Block(
            block['index'],
            block['previous_hash'],
            transactions, block['proof'],
            block['timestamp'])

        self.__chain.append(converted_block)
        stored_transactions = self.__open_transactions[:]

        for itx in block['transactions']:
            for open_tx in stored_transactions:
                if open_tx.sender == itx['sender'] and \
                        open_tx.recipient == itx['recipient'] and \
                        open_tx.amount == itx['amount'] and \
                        open_tx.signature == itx['signature']:
                    try:
                        self.__open_transactions.remove(open_tx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True

    def resolve(self):
        """Checks all peer nodes' blockchains and replaces the local one with
        longer valid ones."""
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                response = requests.get(url)
                node_chain = response.json()

                node_chain = [
                    Block(block['index'],
                          block['previous_hash'],
                          [
                              Transaction(
                                  tx['sender'],
                                  tx['recipient'],
                                  tx['signature'],
                                  tx['amount']) for tx in block['transactions']
                    ],
                        block['proof'],
                        block['timestamp']) for block in node_chain
                ]

                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)

                if node_chain_length > local_chain_length and \
                        Verification.verify_chain(node_chain):
                    winner_chain = node_chain
                    replace = True

            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        # Replace the local chain with the winner chain
        self.chain = winner_chain
        if replace:
            self.__open_transactions = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: The node URL which should be removed.
        """
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        """Return a list of all connected peer nodes."""
        return list(self.__peer_nodes)
