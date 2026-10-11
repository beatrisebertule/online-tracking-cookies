"""
Individual Assignment 1
NWI-IMC074 Online Tracking and Privacy

Student Name:   Beatrise Bertule
Student Number: s1105119
"""

import json
import os
import pandas as pd
import matplotlib.pyplot as plt

from tld import get_fld
from urllib.parse import urlparse, urljoin

# HAR files
HAR_ACCEPT_IN   = "./trekpleister.nl_accept.har"
HAR_REJECT_IN   = "./trekpleister.nl_reject.har"
HAR_UBLOCK_IN   = "./trekpleister.nl_ublock.har"
HAR_ADGUARD_IN  = "./trekpleister.nl_adguard.har"

# JSNON output file
JSON_ACCEPT_OUT  = "./trekpleister.nl_accept.json"
JSON_REJECT_OUT  = "./trekpleister.nl_reject.json"
JSON_UBLOCK_OUT  = "./trekpleister.nl_ublock.json"
JSON_ADGUARD_OUT = "./trekpleister.nl_adguard.json"

VARIANTS = ["accept", "reject", "ublock", "adguard"]
SITE = "https://www.trekpleister.nl/"

# DuckDuckGo Tracker Radar domain
DDG_DOMAIN_MAP_URL = (
    "https://raw.githubusercontent.com/duckduckgo/tracker-radar/"
    "main/build-data/generated/domain_map.json"
)
DDG_DOMAIN_MAP_FILE = "./domain_map.json"

# --------------------------------------------------------------------
# DuckDuckGo Domain Map
# --------------------------------------------------------------------

def load_domain_map():
    """Load the DuckDuckGo domain map from disk."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, DDG_DOMAIN_MAP_FILE), DDG_DOMAIN_MAP_FILE):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)

    import requests  # only needed when the map is not cached yet

    print(f"Downloading DuckDuckGo domain map from {DDG_DOMAIN_MAP_URL} ...")
    resp = requests.get(DDG_DOMAIN_MAP_URL, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        with open(os.path.join(here, DDG_DOMAIN_MAP_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data

def lookup_entity(domain, domain_map):
    """displayName of the entity owning `domain`."""
    labels = domain.lower().split(".")
    for i in range(len(labels) - 1):
        candidate = ".".join(labels[i:])
        info = domain_map.get(candidate)
        if info:
            return info.get("displayName") or info.get("entityName")
    return None

# --------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------

def is_http_url(url:str) -> bool:
    """True for http:// and https:// URLs."""
    return urlparse(url).scheme in ("http", "https")

def is_third_party(page_url:str, request_url:str) -> bool: 
    """True if the two URLs have a different eTLD+1 (effective TLD + 1)."""
    return get_fld(page_url) != get_fld(request_url)
    
def response_received(entry: dict) -> bool:
    """True if a response came back from the intended server.

    Requests blocked by the browser/ad blocker (net::ERR_BLOCKED_BY_CLIENT,
    etc.) have status 0 and no server IP. Error codes such as 404 do count as
    a received response. Responses 'served' by an extension (redirects of
    blocked requests to chrome-extension:// resources) are not from the
    intended server either.
    """
    url = entry["request"]["url"]
    if not is_http_url(url):
        return False
    status = entry.get("response", {}).get("status", 0)
    try:
        status = int(status)
    except (TypeError, ValueError):
        return False
    return status > 0

def header_values(headers, name):
    """All values of a header (case-insensitive)."""
    name = name.lower()
    values = []
    for h in headers or []:
        if h.get("name", "").lower() == name:
            values.extend(v for v in str(h.get("value", "")).split("\n"))
    return values

def parse_set_cookie(line):
    """Parse a single Set-Cookie line into (name, value, attributes_dict)."""
    parts = line.split(";")
    first = parts[0]
    if "=" not in first:
        return None
    name, value = first.split("=", 1)
    attrs = {}
    for p in parts[1:]:
        p = p.strip()
        if not p:
            continue
        if "=" in p:
            k, v = p.split("=", 1)
            attrs[k.strip().lower()] = v.strip()
        else:
            attrs[p.lower()] = ""
    return name.strip(), value.strip(), attrs

# --------------------------------------------------------------------
# Part II: HAR File Info Extraction
# --------------------------------------------------------------------

def get_num_requests(har: dict) -> int:
    """(1) Number of requests that received a response."""
    entries = har["log"]["entries"]
    received = [entry
                for entry in entries 
                if response_received(entry)] # check if a response was received
    return len(received)

# TODO: double check
def get_num_cross_domain_redirections(har:dict) -> int:
    """(2) Number of 3XX redirects to a URL with a different eTLD+1, 
    excluding redirects to chrome-extension:// URLs."""
    count = 0
    entries = har["log"]["entries"]
    for entry in entries:
        page_url = entry["request"]["url"]
        resp = entry["response"]
        status = resp["status"]
        
        if not 300 <= status < 400: # only HTTP redirects (3XX) 
            continue
        
        location = None
        headers = resp.get("headers", [])
        for header in headers:
            if header["name"].lower() == "location":
                location = header["value"]
                break  
            
        if not location:
            continue
        
        redirect_url = urljoin(page_url, location) # resolve relative redirects
        if redirect_url.startswith("chrome-extension://"): # exclude chrome-extension:// redirects 
            continue
        if is_third_party(page_url, redirect_url):
            count += 1
    return count


def get_num_requests_w_cookies(har: dict) -> int:
    """(3) Number of requests with a non-empty Cookie header."""
    count = 0
    for entry in har["log"]["entries"]:
        for header in entry["request"]["headers"]:
            if header["name"].lower() == "cookie" and header["value"] != "" and response_received(entry): # check if a response was received
                count += 1
                break
    return count

def get_num_responses_w_cookies(har: dict) -> int:
    """(4) Number of responses with a non-empty Set-Cookie header."""
    count = 0
    for entry in har["log"]["entries"]:
        for header in entry["response"]["headers"]:
            if header["name"].lower() == "set-cookie" and header["value"] != "":
                count += 1
                break
    return count

def get_third_party_domain(har: dict) -> list:
    """(5) Distinct third-party domains contacted."""
    third_party_hostnames = set()
    entries = har["log"]["entries"]
    # page_url = har["log"]["pages"][0]["title"]
    page_url = SITE # hardcoded for adguard file, as page title entry does not exist
    
    for entry in entries:
        req_url = entry["request"]["url"]
        if is_third_party(page_url, req_url) and response_received(entry): # check if a response was received
            third_party_hostnames.add(urlparse(req_url).hostname)
    return list(third_party_hostnames)

def get_server_ips(har: dict) -> list:
    """(6) Server IP addresses contacted (IPv6 brackets stripped)."""
    entries = har["log"]["entries"]
    server_ips = [ entry["serverIPAddress"].strip("[]") 
                   for entry in entries 
                   if entry.get("serverIPAddress", "").strip("[]") # only return non empty IP address values
    ] 
    return server_ips

def get_potential_tracking_cookies(har: dict) -> list:
    """(7) Distinct (cookie name, cookie value, request domain) tuples for
    cookies set with SameSite=None. Parsed from the Set-Cookie response headers."""
    tracking = set()
    entries = har["log"]["entries"]
    
    for entry in entries:
            req_domain = get_fld(entry["request"]["url"])
            for cookie in header_values(entry["response"].get("headers"), "set-cookie"): # return (response) header values that have key (name) "set-cookie"
                parsed = parse_set_cookie(cookie)
                if not parsed:
                    continue
                name, value, attrs = parsed
                if attrs.get("samesite", "").strip().lower() == "none": # filter and return only cookies with flag SameSite= None
                    tracking.add((name, value, req_domain))
    return sorted(tracking)
    
def get_third_party_entities(third_party_domains: list, domain_map:dict) -> list:
    """(8) Distinct entities owning the third-party domains.
    Domains not in the DuckDuckGo map are skipped."""
    entities = set()
    for domain in third_party_domains:
        ent = lookup_entity(domain, domain_map)
        if ent: # skip None (unknown domain)
            entities.add(ent)
    return list(entities)

def get_post_request_origins(har: dict) -> list:
    """(9) Distinct domains that received one or more POST requests."""
    post_domains = set()
    entries = har["log"]["entries"]
    received = [ entry
                 for entry in entries
                 if response_received(entry) ] # check if a response was received
    for entry in received:
        if entry["request"]["method"] == "POST":
            domain = get_fld(entry["request"]["url"])
            post_domains.add(domain)
    return list(post_domains)

# --------------------------------------------------------------------
# Part III Result PLots
# --------------------------------------------------------------------


def plot_metrics():
    """Read the four Part 2 JSON files and create barplots for each metric."""

    json_files = {
        "accept": JSON_ACCEPT_OUT,
        "reject": JSON_REJECT_OUT,
        "ublock": JSON_UBLOCK_OUT,
        "adguard": JSON_ADGUARD_OUT
    }
    
    variants = {
        "accept":  (HAR_ACCEPT_IN, JSON_ACCEPT_OUT),
        "reject":  (HAR_REJECT_IN, JSON_REJECT_OUT),
        "ublock":  (HAR_UBLOCK_IN, JSON_UBLOCK_OUT),
        "adguard": (HAR_ADGUARD_IN, JSON_ADGUARD_OUT)
    }

    results = {}

    # Read all four JSON files
    for variant, filepath in json_files.items():
        with open(filepath, "r", encoding="utf-8") as f:
            results[variant] = json.load(f)

    variants = list(results.keys())

    num_requests = [
        results[variant]["num_requests"]
        for variant in variants
    ]

    num_cross_domain_redirections = [
        results[variant]["num_cross_domain_redirections"]
        for variant in variants
    ]

    num_third_party_domains = [
        len(results[variant]["third_party_domains"])
        for variant in variants
    ]

    num_third_party_entities = [
        len(results[variant]["third_party_entities"])
        for variant in variants
    ]

    num_server_ips = [
        len(results[variant]["server_ips"])
        for variant in variants
    ]

    num_potential_tracking_cookies = [
        len(results[variant]["potential_tracking_cookies"])
        for variant in variants
    ]

    # store all metrics in one dictionary
    metrics = {
        "num_requests": ("Number of Requests", num_requests),
        "num_third_party_domains": ("Number of Third-Party Domains", num_third_party_domains),
        "num_third_party_entities": ("Number of Third-Party Entities", num_third_party_entities),
        "num_cross_domain_redirections": ("Number of Cross-Domain Redirections", num_cross_domain_redirections),
        "num_server_ips": ("Number of Server IPs", num_server_ips),
        "num_potential_tracking_cookies": ("Number of Potential Tracking Cookies", num_potential_tracking_cookies)
    }

    
    # create one barplot for each metric
    for metric_name, (title, values) in metrics.items():

        fig, ax = plt.subplots(figsize=(8, 5))

        bars = ax.bar(
            variants,
            values,
            width=0.6,
            # color=["#4C78A8", "#F58518", "#54A24B", "#E45756"] #multi-color
            # color=["#D9A3A3", "#C77C7C", "#A95656", "#843C3C"] # tones of red
            color=["#A9C8A3","#82A87B","#5D8257","#3B542E"] # tones of green
        ) 

        # Title and axis labels
        ax.set_title(
            title,
            fontsize=14,
            # fontweight="bold",
            pad=15
        )

        ax.set_xlabel(
            "HAR File Variant",
            fontsize=12,
            labelpad=8
        )

        ax.set_ylabel(
            "Count",
            fontsize=12,
            labelpad=8
        )

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax.grid(
            axis="y",
            linestyle="--",
            alpha=0.4
        )

        ax.set_axisbelow(True)

        # Add values above bars
        max_value = max(values) if values else 0

        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + max_value * 0.02,
                str(value),
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold"
            )

        # Give the bars some space above the highest value
        if max_value > 0:
            ax.set_ylim(0, max_value * 1.15)

        plt.tight_layout()

        # Save using the variable name
        plt.savefig(
            f"./plots/plot_{metric_name}.pdf",
            dpi=300,
            bbox_inches="tight"
        )


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------

if __name__ == "__main__":
    variants = {
        "accept": (HAR_ACCEPT_IN, JSON_ACCEPT_OUT),
        "reject": (HAR_REJECT_IN, JSON_REJECT_OUT),
        "ublock": (HAR_UBLOCK_IN, JSON_UBLOCK_OUT),
        "adguard": (HAR_ADGUARD_IN, JSON_ADGUARD_OUT)
    }
    
    domain = DDG_DOMAIN_MAP_FILE
    with open(domain, "r", encoding="utf-8") as f:
        domain_map = json.load(f)
    
    for variant, (data_in, data_out) in variants.items():

        print(f"\nProcessing {variant}...")

        with open(data_in, "r", encoding="utf-8") as f:
            har = json.load(f)

        # (1)-(4) counts
        num_requests = get_num_requests(har)
        num_cross_domain_redirections = get_num_cross_domain_redirections(har)
        num_requests_w_cookies = get_num_requests_w_cookies(har)
        num_responses_w_cookies = get_num_responses_w_cookies(har)

        # (5)-(9) lists
        third_party_domains = sorted(
            list(set(get_third_party_domain(har)))
        )

        server_ips = sorted(
            list(set(get_server_ips(har)))
        )

        potential_tracking_cookies = sorted(
            list(set(get_potential_tracking_cookies(har)))
        )

        third_party_entities = sorted(
            get_third_party_entities(third_party_domains, domain_map)
        )

        post_request_origins = sorted(
            get_post_request_origins(har)
        )

        # compose JSON results file
        final = {
            "num_requests": num_requests,
            "num_cross_domain_redirections": num_cross_domain_redirections,
            "num_requests_w_cookies": num_requests_w_cookies,
            "num_responses_w_cookies": num_responses_w_cookies,
            "third_party_domains": third_party_domains,
            "server_ips": server_ips,
            "potential_tracking_cookies": potential_tracking_cookies,
            "third_party_entities": third_party_entities,
            "post_request_origins": post_request_origins
        }

        # save 
        with open(data_out, "w", encoding="utf-8") as f:
            json.dump(final, f, indent=4)

        print(f"Saved: {data_out}")
    
    plot_metrics()
    print("\nPlots generated and saved.")