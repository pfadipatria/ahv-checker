import os
import re

import requests
from art import tprint
from dotenv import load_dotenv
from tqdm import tqdm
from bs4 import BeautifulSoup

load_dotenv()

api_key = os.getenv("API_KEY")
group = os.getenv("GROUP")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

BASE_URL = "https://db.scout.ch"
ATTRIBUTE_TO_CHECK = "ahv_number"

s = requests.Session()


def get_groupname(group_id):
    group = s.get(f"{BASE_URL}/groups/{group_id}.json").json()
    return group["groups"][0]["name"]


def get_all_sub_groups(group_id, depth=0):
    group = s.get(f"{BASE_URL}/groups/{group_id}.json").json()
    group_name = group["groups"][0]["name"]
    try:
        children = group["groups"][0]["links"]["children"]
    except KeyError:
        children = []
    subgroups = []
    for child in (
        tqdm(children, desc=f"Fetching subgroups of {group_name}", unit="group")
        if depth == 0
        else children
    ):
        subgroups.extend(get_all_sub_groups(child, depth + 1))
    subgroups.append(group_id)
    return list(set(subgroups))


def get_people_id_from_group(group_id):
    people = s.get(f"{BASE_URL}/groups/{group_id}/people.json").json()["people"]
    return [person["id"] for person in people]


def get_people_details(group_id, person_id):
    person = s.get(f"{BASE_URL}/groups/{group_id}/people/{person_id}.json").json()
    return person["people"][0]


def name_formatter(nickname, firstname, lastname):
    if nickname:
        return f"{nickname} / {firstname} {lastname}"
    return f"{firstname} {lastname}"

tprint("AHV-Checker")

# Login procedure
login_page = s.get("https://db.scout.ch/de/users/sign_in")

soup = BeautifulSoup(login_page.content, "html.parser")
hidden_tag = soup.find(attrs={"name": "authenticity_token"})
auth_token = hidden_tag.attrs["value"]

login = s.post(
    "https://db.scout.ch/de/users/sign_in",
    {
        "authenticity_token": auth_token,
        "person[email]": username,
        "person[password]": password,
    },
)

groups = get_all_sub_groups(group)
people_ids = []
for group in tqdm(groups, desc=f"Fetching all people ids", unit="group"):
    people_ids.extend([(group, p_id) for p_id in get_people_id_from_group(group)])

people_ids = list(set(people_ids))  # Ensure only unique

people = []
for person_id, group_id in tqdm(
    people_ids, desc=f"Fetching all peoples info", unit="lookups"
):
    people.append(get_people_details(person_id, group_id))

people.sort(key=lambda p: p["last_name"].replace("von ", "") + p["first_name"])

ahv_regex = re.compile("\d{3}.\d{4}.\d{4}.\d{2}")

people_without_ahv = [
    person
    for person in people
    if not (person[ATTRIBUTE_TO_CHECK] and ahv_regex.match(person[ATTRIBUTE_TO_CHECK]))
]

print(f"Mit AHV-Nr: {len(people) - len(people_without_ahv)}")
print(f"Ohne AHV-Nr: {len(people_without_ahv)}")
print(f"Total: {len(people)}")
print()

for p in people_without_ahv:
    f_name = name_formatter(p["nickname"], p["first_name"], p["last_name"])
    url = p["href"].replace(".json", "")
    print(f"{f_name}: {url}")
