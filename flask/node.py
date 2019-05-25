from flask import Flask, jsonify, request
from flask_cors import CORS

from wallet import Wallet
from blockChain import Blockchain

app = Flask(__name__)
wallet = Wallet()
blockchain = Blockchain(wallet.public_key)
CORS(app)


@app.route('/wallet', methods=['POST'])
def create_keys():
    wallet.create_keys()
    if wallet.save_keys():
        global blockchain
        blockchain = Blockchain(wallet.public_key)
        response = {
            'funds': blockchain.get_balance(),
            'public_key': wallet.public_key,
            'private_key': wallet.private_key
        }
        return jsonify(response), 201
    else:
        response = {
            'message': "Saving the keys failed"
        }
        return jsonify(response), 500


@app.route('/wallet', methods=['GET'])
def load_keys():
    if wallet.load_keys():
        global blockchain
        blockchain = Blockchain(wallet.public_key)
        response = {
            'public_key': wallet.public_key,
            'private_key': wallet.private_key,
            'my_funds': blockchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': "Loading the keys failed"
        }
        return jsonify(response), 500
    pass


@app.route('/balance', methods=['GET'])
def balance():
    balance = blockchain.get_balance()
    if balance != None:
        response = {
            'my_funds': balance,
            'message': "Balance Fetched Sucessfully"
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Loading wallet failed',
            'wallet_set_up': wallet.public_key != None
        }
        return jsonify(response), 500


@app.route('/', methods=['GET'])
def get_UI():
    return 'Working'


@app.route('/transaction', methods=['POST'])
def add_transaction():
    if wallet.public_key == None:
        response = {
            'Message': 'No data found'
        }
        return jsonify(response), 400
    values = request.get_json()
    if not values:
        response = {
            'message': "No data found"
        }
        return jsonify(response), 400
    required_field = ['recipient', 'amount']
    if not all(field for field in required_field):
        response = {
            'message': 'Required String missing'
        }
        return response, 400
    recipient = values['recipient']
    amount = values['amount']
    signature = wallet.sign_transaction(wallet.public_key, recipient, amount)
    success = blockchain.add_transaction(recipient, wallet.public_key, signature, amount)
    if success:
        response = {
            'message': "Sucessfully added transaction",
            'transaction': {
                'sender': wallet.public_key,
                'recipient': recipient,
                'amount': amount,
                'signature': signature
            },
            'funds': blockchain.get_balance()
        }
        return jsonify(response), 201
        
    else:
        response = {
            'message': "Creating a transaction failed"
        }
        return jsonify(response), 500

@app.route('/mine', methods=['POST'])
def mine():
    block = blockchain.mine_block()

    if block != None:
        dict_block = block.__dict__.copy()
        dict_block['transactions'] = [
            tx.__dict__ for tx in dict_block['transactions']]
        response = {
            'message': 'Block Added Sucessfully',
            'block': dict_block,
            'current_funds': blockchain.get_balance()
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Adding block failed',
            'wallet_set_up': wallet.public_key != None

        }
        return jsonify(response), 500


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_data = blockchain.chain
    dict_chain = [block.__dict__.copy() for block in chain_data]
    for dict_block in dict_chain:
        dict_block['transactions'] = [
            tx.__dict__ for tx in dict_block['transactions']]
    return jsonify(dict_chain), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
