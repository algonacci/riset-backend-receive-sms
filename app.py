from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/api/data', methods=['GET'])
def get_data():
    # Sample data to return
    data = {
        'message': 'Hello, World!',
        'status': 'success'
    }
    return jsonify(data)

# create some post endpoint
@app.route('/api/data', methods=['POST'])
def post_data():
    # Get the JSON data from the request
    data = request.get_json()
    
    # Process the data (for demonstration, we'll just echo it back)
    response = {
        'received_data': data,
        'status': 'success'
    }
    return jsonify(response), 201

if __name__ == '__main__':
    app.run(debug=True)