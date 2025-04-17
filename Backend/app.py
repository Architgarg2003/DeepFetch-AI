from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import re
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain_google_genai import ChatGoogleGenerativeAI
from serpapi import search

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Set up API keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# API Key Checks
if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables.")
if not SERPAPI_API_KEY:
    print("Error: SERPAPI_API_KEY not found in environment variables.")

# Set up conversation memory
memory = ConversationBufferMemory()

# Initialize LLM
llm = None
if GOOGLE_API_KEY:
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.6, # Slightly lower temp might help follow formatting instructions
            # Consider adding safety settings if needed
            # safety_settings={...}
        )
        print("Gemini LLM Initialized.")
    except Exception as e:
        print(f"Error initializing Gemini LLM: {e}")
else:
    print("Cannot initialize Gemini LLM due to missing GOOGLE_API_KEY.")

# Initialize ConversationChain
conversation = None
if llm:
    conversation = ConversationChain(
        llm=llm,
        memory=memory,
        verbose=False # Quieter output unless debugging
    )
    print("ConversationChain Initialized.")
else:
    print("ConversationChain cannot be initialized because LLM is not available.")


def search_and_retrieve(query, num_results=5):
    """
    Uses SerpApi to get search results (organic links).
    """
    if not SERPAPI_API_KEY:
        print("Error: SerpApi API key is missing.")
        return []

    params = {
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "engine": "google",
        "num": num_results,
        "hl": "en",
        "gl": "us"
    }

    try:
        print(f"Performing SerpApi search for: {query}")
        search_results = search(params)

        urls = []
        if "organic_results" in search_results:
            for result in search_results["organic_results"]:
                if "link" in result:
                    urls.append(result["link"])
                if len(urls) >= num_results:
                    break
            print(f"Found URLs: {urls}")
            return urls
        else:
            print("Warning: 'organic_results' not found in SerpApi response.")
            print(f"SerpApi response keys: {search_results.keys() if isinstance(search_results, dict) else 'Not a dict'}")
            return []

    except Exception as e:
        print(f"Error during SerpApi search: {e}")
        return []

def extract_content(url):
    """
    Extract meaningful text content from a web page.
    (Includes robustness improvements from previous step)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15, stream=True, verify=True)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' not in content_type:
            print(f"Skipping non-HTML content at {url} (Content-Type: {content_type})")
            return ""

        max_read_size = 5 * 1024 * 1024 # 5 MB limit
        html_content_bytes = response.raw.read(max_read_size, decode_content=True)

        if len(html_content_bytes) == max_read_size:
            print(f"Warning: Content possibly truncated for {url} (reached {max_read_size} bytes)")

        # Decoding logic
        html_content = ""
        detected_encoding = response.encoding if response.encoding else response.apparent_encoding
        try:
            if detected_encoding:
                html_content = html_content_bytes.decode(detected_encoding, errors='replace')
            else:
                 # Fallback to utf-8 if detection fails
                 html_content = html_content_bytes.decode('utf-8', errors='replace')
                 print(f"Warning: No encoding detected for {url}, falling back to UTF-8.")
        except Exception as decode_err:
             print(f"Error decoding content from {url} with encoding {detected_encoding}: {decode_err}. Trying UTF-8.")
             try: # Try UTF-8 as a last resort
                 html_content = html_content_bytes.decode('utf-8', errors='replace')
             except Exception as final_decode_err:
                 print(f"FATAL: Could not decode content from {url} even with UTF-8: {final_decode_err}")
                 return "" # Give up if decoding fails completely

        soup = BeautifulSoup(html_content, 'html.parser')

        for element in soup(["script", "style", "footer", "nav", "header", "aside", "form", "button", "input", "select", "textarea", "label", "iframe", "noscript", ".sidebar", ".ad", ".advertisement", ".popup", ".modal"]):
            if hasattr(element, 'decompose'):
                 element.decompose()

        main_elements = soup.select('main, article, [role="main"], .main-content, #main-content, .post-content, .article-content, .entry-content')
        if main_elements:
            main_element = max(main_elements, key=lambda x: len(x.get_text(strip=True)))
            text = main_element.get_text(separator='\n', strip=True)
        else:
            body = soup.find('body')
            text = body.get_text(separator='\n', strip=True) if body else ""

        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text_content = '\n'.join(chunk for chunk in chunks if len(chunk) > 15) # Increased min length slightly

        text_content = re.sub(r'\n{3,}', '\n\n', text_content)
        text_content = re.sub(r'[ \t]+', ' ', text_content)

        max_content_length = 10000
        if len(text_content) > max_content_length:
            text_content = text_content[:max_content_length] + "...[Content truncated]"

        return text_content

    except requests.exceptions.Timeout:
        print(f"Timeout error extracting content from {url}")
        return ""
    except requests.exceptions.RequestException as e:
        # Log specific HTTP errors if possible
        status_code = e.response.status_code if e.response else 'N/A'
        print(f"Request error extracting content from {url} (Status: {status_code}): {e}")
        return ""
    except Exception as e:
        print(f"General error extracting content from {url}: {e}")
        return ""

def process_content(urls, query):
    """
    Process the content from multiple URLs and prepare it for the LLM.
    """
    all_content = []
    processed_count = 0
    processed_urls = [] # Keep track of URLs where content was successfully extracted

    for url in urls:
        print(f"Processing content from: {url}")
        content = extract_content(url)
        if content:
            # Store URL with content for later potential use by LLM
            all_content.append(f"Source URL: {url}\n\n{content}\n\n---\n\n")
            processed_urls.append(url) # Add to list of successfully processed URLs
            processed_count += 1
        else:
            print(f"No meaningful content extracted from: {url}")

    if not all_content:
        print("No relevant content found from any source.")
        return "No relevant content found from the search results.", [] # Return empty list for processed URLs

    print(f"Successfully processed content from {processed_count}/{len(urls)} URLs.")
    combined_content = "".join(all_content)

    max_combined_length = 28000 # Gemini 1.5 Flash has a large context, adjust if needed
    if len(combined_content) > max_combined_length:
        print(f"Combined content length ({len(combined_content)}) exceeds limit ({max_combined_length}). Truncating.")
        combined_content = combined_content[:max_combined_length] + "...[Combined Content truncated due to length]"

    # Return the combined content AND the list of URLs that actually yielded content
    return combined_content, processed_urls


# --- THIS IS THE MAIN CHANGE ---
def generate_response(content, query, source_urls_with_content):
    """
    Generate a response using Gemini based on the content and query.
    Instructs the LLM to list sources at the end.
    """
    if not conversation:
        print("Error: ConversationChain is not initialized. Cannot generate response.")
        return "Sorry, the AI assistant is not available right now."

    try:
        # Modified Prompt for end-of-response source listing
        prompt = f"""
        You are an AI assistant designed to answer user queries based *only* on the provided web search context.
        Analyze the following web search results carefully. Each result starts with "Source URL: [url]".
        Synthesize the information to provide a comprehensive, accurate, and neutral response to the user's query.
        Focus on information directly present in the provided text snippets.
        Do not add information not found in the context. Do not make assumptions or inferences beyond the text.
        If the provided context does not contain sufficient information to answer the query thoroughly, clearly state that the information is limited or not available in the search results.
        Structure the response clearly. Use bullet points or numbered lists if appropriate for readability.
        **Do NOT include inline source citations like [Source: url] within the main body of your answer.**

        USER QUERY: "{query}"

        PROVIDED WEB SEARCH CONTEXT:
        --- START CONTEXT ---
        {content}
        --- END CONTEXT ---

        Based *only* on the context above, answer the user query.
        """

        print(f"Generating response for query: {query} (Sources to be listed at end)")
        response = conversation.predict(input=prompt)
        print("LLM Response Generated.")

        # --- Optional: Post-processing to ensure sources are present ---
        # This is a fallback in case the LLM forgets the source list.
        # It appends ALL processed source URLs if the LLM didn't add any.
        # if "\nSources:\n" not in response and source_urls_with_content:
        #      print("LLM did not include sources section, adding fallback list.")
        #      sources_list_str = "\n\n---\nSources:\n" + "\n".join(f"- {url}" for url in source_urls_with_content)
        #      response += sources_list_str
        # -------------------------------------------------------------

        return response
    except Exception as e:
        print(f"Error generating response with LLM: {e}")
        # import traceback # Uncomment for debugging
        # traceback.print_exc() # Uncomment for debugging
        return "Sorry, I encountered an error while processing your request with the AI model. Please try again."
# --- END OF MAIN CHANGE ---


@app.route('/api/query', methods=['POST'])
def handle_query():
    if not llm or not conversation:
         return jsonify({"error": "AI service is not properly configured or initialized."}), 503

    data = request.json
    if not data or 'query' not in data:
        return jsonify({"error": "No query provided"}), 400

    query = data['query']
    print(f"\n--- New Query Received: {query} ---")

    # Step 1: Search for URLs
    initial_urls = search_and_retrieve(query)

    if not initial_urls:
        print("Search returned no URLs.")
        return jsonify({
            "response": "I couldn't find relevant web pages for your query using the search service. Please try rephrasing your query.",
            "sources": [] # Return empty list
        })

    # Step 2: Extract content and get the list of URLs that actually had content
    content, urls_with_content = process_content(initial_urls, query) # Now returns URLs with content

    if not content or not urls_with_content: # Check if content extraction yielded anything
         print("No content could be extracted from the found URLs.")
         return jsonify({
             "response": "I found some web pages, but I couldn't extract useful information from them to answer your query.",
             "sources": initial_urls # Provide the originally found URLs
         })

    # Step 3: Generate response using content AND the list of successful URLs (for fallback)
    response = generate_response(content, query, urls_with_content)

    # Step 4: Return response and the *initial* list of URLs found by search
    print(f"Final response generated. Sending to client.")
    return jsonify({
        "response": response, # This string now contains the answer AND the sources list at the end
        "sources": initial_urls # This list contains all URLs initially found by SerpApi
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    status = {
        "status": "ok",
        "llm_initialized": llm is not None,
        "conversation_initialized": conversation is not None,
        "serpapi_key_present": SERPAPI_API_KEY is not None,
        "google_api_key_present": GOOGLE_API_KEY is not None
    }
    http_status = 200 if llm and conversation and SERPAPI_API_KEY and GOOGLE_API_KEY else 503
    return jsonify(status), http_status


if __name__ == '__main__':
    if not GOOGLE_API_KEY or not SERPAPI_API_KEY or not llm or not conversation:
        print("\nFATAL ERROR: One or more API keys are missing or components failed to initialize.")
        print(f"  - Google API Key Present: {bool(GOOGLE_API_KEY)}")
        print(f"  - SerpApi Key Present: {bool(SERPAPI_API_KEY)}")
        print(f"  - LLM Initialized: {bool(llm)}")
        print(f"  - Conversation Initialized: {bool(conversation)}")
        print("Exiting due to configuration errors.\n")
        # exit(1) # Optional: Force exit if you prefer
    else:
        print("\nConfiguration OK. Starting Flask server...")
        # app.run(host='0.0.0.0', port=5000, debug=False) # Use debug=False for production
        app.run()