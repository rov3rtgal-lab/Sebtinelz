from flask import Flask, request, jsonify
import requests
app = Flask(__name__)

@app.route("/search-law")
def search_law_api():
    query = request.args.get("q")

    url = "https://www.courtlistener.com/api/rest/v4/search/"
    params = {"q": query, "type": "o"}

    response = requests.get(url, params=params)
    return jsonify(response.json())
if __name__ == "__main__":
    app.run(debug=True)