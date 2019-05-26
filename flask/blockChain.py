from functools import reduce
import hashlib
import json
import requests

from utility.hash_utils import hash_block
from utility.verification import Verification
from block import Block
from transaction import Transaction
from wallet import Wallet

# The reward given to the miners (for creating a new block).
MINING_REWARD = 10


class Blockchain:
    def __init__(self, public_key, node_ID):
        # The starting block of blockchain.
        genesis_block = Block(0, "", [], 100, 0)
        # Initailizing our (empty) blockchain list.     Making it private.
        self.chain = [genesis_block]
        # Unhandeled transaction.                       Making it private.
        self.__open_transaction = list()
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_ID
        self.load_data()

    @property
    def chain(self):
        return self.__chain[:]

    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transaction(self):
        return self.__open_transaction[:]

    def load_data(self):
        """Initialize by loading data from a file"""
        try:

            with open("blockchain-{}.txt".format(self.node_id), mode='r') as file:
                file_content = file.readlines()

                # To remove the "\n" from the load, we are using range selector.
                blockchain = json.loads(file_content[0][:-1])
                updated_blockchain = list()

                for block in blockchain:
                    converted_tx = [Transaction(
                        tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
                    updated_block = Block(
                        block['index'], block['previous_hash'], converted_tx, block['proof'], block['timestamp'])
                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transaction = json.loads(file_content[1][:-1])
                updated_transactions = list()
                for tx in open_transaction:
                    updated_transaction = Transaction(
                        tx['sender'], tx['recipient'], tx['signature'], tx['amount'])
                    updated_transactions.append(updated_transaction)
                self.__open_transaction = updated_transactions
                peer_nodes = json.loads(file_content[2])
                self.__peer_nodes = set(peer_nodes)

        except (IOError, IndexError):
            print("Exception HANDLED")
            pass

    def save_data(self):
        try:
            # We can use any extension.
            with open("blockchain-{}.txt".format(self.node_id), mode='w') as file:
                new_saveable_chain = [block.__dict__ for block in [Block(new_block.index, new_block.previous_hash, [
                    tx.__dict__ for tx in new_block.transactions], new_block.proof, new_block.timestamp) for new_block in self.__chain]]
                file.write(json.dumps(new_saveable_chain))
                file.write('\n')
                new_saveable_tx = [
                    block.__dict__ for block in self.__open_transaction]
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
        while not Verification.valid_proof(self.__open_transaction, last_hash, proof):
            proof += 1
            # Printing the number of hashes done to check the proof.
            # print(proof)
        return proof

    def get_balance(self, sender=None):
        """Calculate and return balance of the participant.
        """
        if sender == None:
            if self.public_key == None:
                return None
            participant = self.public_key
        else:
            participant = sender

        tx_sender = [[tx.amount for tx in block.transactions
                      if tx.sender == participant] for block in self.__chain]
        open_tx_sender = [tx.amount
                          for tx in self.__open_transaction if tx.sender == participant]
        tx_sender.append(open_tx_sender)
        print(tx_sender)
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                             if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)

        tx_recipient = [[tx.amount for tx in block.transactions
                         if tx.recipient == participant] for block in self.__chain]
        amount_recieved = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
                                 if len(tx_amt) > 0 else tx_sum + 0, tx_recipient, 0)
        # Returns total balance.
        return amount_recieved - amount_sent

    def get_last_blockchain_value(self):
        """Returns the last value of the current blockchain."""
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    def add_transaction(self, recipient, sender, signature, amount=1.0, is_receiving= False):
        """Append new value as well as last value to blockchain.

        Arguments:
            :sender: The sender of the coin.
            :recipient: The recipient of the coin.
            :amount: The amount of coin sent with the transaction (default = 1.0).
            :signature: The signature of the sender.
        """
        if self.public_key == None:
            return False

        transaction = Transaction(sender, recipient, signature, amount)
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transaction.append(transaction)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url, json={
                            'sender': sender, 'recipient': recipient, 'amount': amount, 'signature': signature})
                        if response.status_code == 400 or response.status_code == 500:
                            print('Transaction declined, needs to resolve')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def mine_block(self):
        if self.public_key == None:
            return None

        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        # print(hashed_block)
        proof = self.proof_of_work()
        # Miners should be rewarded for there work.
        reward_transaction = Transaction(
            "MINING", self.public_key, '', MINING_REWARD)
        # Copy transaction instead of manipulating the orignal "open_transactions".
        copied_transaction = self.__open_transaction[:]
        for tx in copied_transaction:
            if not Wallet.verify_transaction(tx):
                return None
        copied_transaction.append(reward_transaction)
        block = Block(len(self.__chain), hashed_block,
                      copied_transaction, proof)

        self.__chain.append(block)
        # Resets the open_transaction to an empty list.
        self.__open_transaction = []
        self.save_data()
        return block

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: Node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def check_peer_nodes(self, node):
        """Check whether the node exists or not"""
        if node in self.__peer_nodes:
            return self.__peer_nodes
        else:
            return False

    def remove_peer_nodes(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: Node URL which should be removed.
        """
        if self.check_peer_nodes(node):
            self.__peer_nodes.discard(node)
            self.save_data()
            return True
        else:
            self.save_data()
            return False

    def get_peer_nodes(self):
        """Return list of all connected peer nodes."""
        return list(self.__peer_nodes)
