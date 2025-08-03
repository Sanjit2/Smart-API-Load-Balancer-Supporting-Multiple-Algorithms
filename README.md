# ⚖️ TCP Load Balancer with Multiple Distribution Algorithms

A powerful and extensible **TCP Load Balancer** built in Python, supporting **Round Robin**, **Least Connections**, and **Least Response Time** algorithms. This project also integrates the **Google Search API** for secure query handling over **SSL/TLS**, with features like real-time health checks, performance analytics, and query caching.

---

## 🚀 Features

- 🔁 **Multiple Load Balancing Algorithms**
  - Round Robin
  - Least Connections
  - Least Response Time (RTT-based)

- 🔒 **SSL/TLS Secure Communication**
  - All client-server traffic is encrypted using Python’s built-in `ssl` module.

- 🔍 **Google Search API Integration**
  - Handles search queries using Google's programmable search API.

- 🧠 **Real-time Health Checks**
  - Automatically detects and bypasses failed or slow servers.

- ⚡ **Query Caching**
  - Reduces latency and load by caching frequently searched queries.

---

## 🔑 API Key Setup

> ⚠️ Before running the servers, you **must insert your Google Programmable Search API Key and Search Engine ID** inside both `server1.py` and `server2.py`.

Open both files and update the following variables:
```python
API_KEY = "YOUR_GOOGLE_API_KEY"
SEARCH_ENGINE_ID = "YOUR_SEARCH_ENGINE_ID"
