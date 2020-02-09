# Get authors for TILS-WG
import os
from pandas import DataFrame, read_csv, concat

## Ground work

#### Read files

# This is the big working group csv file
TILWG = read_csv('./TILWG.csv')

# These are my authors and affiliations
with open('./my_authors.txt', 'r') as f:
    MY_AUTHORS = f.read()
    MY_AUTHORS = MY_AUTHORS.splitlines()

with open('./my_affiliations.txt', 'r') as f:
    MY_AFFILIATIONS = f.read()
    MY_AFFILIATIONS = MY_AFFILIATIONS.splitlines()

#### Some clanup, quality checks, etc. etc.

# This is list of my authors (just author names)
my_authors = [
    [k.strip() for k in j.split(' | ')] for j in MY_AUTHORS]

# same for big WG
tilwg_authors = [str(j).strip() for j in list(TILWG.loc[:, 'auth'])]
TILWG.loc[:, 'auth'] = tilwg_authors

# DATA INTEGRITY CHECK!!!!!!
# find commmon authors, keeping in mind there might be some different
# capitalization & middle initials


def _get_common_authors():
    common_authors = tilwg_authors.copy()
    nchar1 = 3
    nchar2 = 4
    # union is a dict where keys are full-wg spelling, and values
    # are my spelling.
    union = dict()
    manual = []
    for smy, _ in my_authors:
        my = [j.lower() for j in smy.strip().split(' ')]
        matched = False
        for sfull in tilwg_authors:
            full = [j.lower() for j in sfull.strip().split(' ')]
            first = my[0][:nchar1] == full[0][:nchar1]
            last = my[-1][:nchar2] == full[-1][:nchar2]
            if first and last:
                common_authors.remove(sfull)
                union[sfull] = smy
                matched = True
        if not matched:
            manual.append(smy)
    manual = list(set(manual))
    return union, manual


def _sanity_checks():
    assert (len(union) == len(my_authors)), \
        "Suspiciously duplicate authors found in main TIL-WG!"
    assert (len(manual) == 0), "These authors need manual fixing: %s" % manual

    # print authors with misspellings -- my author list is reference point
    need_updating = [v for k, v in union.items() if k != v]
    if len(need_updating) > 0:
        show = "The following authors are misspelt in main TIL-WG:"
        show += "\n".join(need_updating)
        raise Exception(show)


# ideally, manual should be empty since all out authors are TILs-WG member
# if not you should manually fix those in manual
union, manual = _get_common_authors()
need_updating = _sanity_checks()

#### Combine author and member lists


def _combine_author_and_member_tables():
    # remove authors from the full-wg already in author list
    tilwg = TILWG.loc[~TILWG.loc[:, 'auth'].isin(union.keys()), :]

    # now sort non-author member alphabetically as journal wants
    tilwg.sort_values('auth', inplace=True, ascending=True)

    # dict mapping affiliation number strings and institutions
    my_affiliations = dict()
    for aff in MY_AFFILIATIONS:
        start = aff.find('.')
        my_affiliations[aff[:start].strip()] = aff[start + 1:].strip()

    # create a dataframe for my authors in the same form as main group
    my_df = DataFrame(columns=('auth', 'affil'))
    for smy, affs in my_authors:
        afflist = [j.strip() for j in affs.split(',')]
        for aff in afflist:
            pos = my_df.shape[0]
            my_df.loc[pos, 'auth'] = smy
            my_df.loc[pos, 'affil'] = my_affiliations[aff]

    # now concat the two to form the big list
    # It's important we do things this way to preserve the order of authors
    FULLDF = concat((my_df, tilwg), 0, ignore_index=True)
    first_member = len(my_df)

    return FULLDF, first_member


FULLDF, first_member = _combine_author_and_member_tables()


#### Inspect + standardize affiliations


# affiliations that we KNOW are not duplicted. This is determined
# post-hoc after running the function below and manually inspecting results
NOT_SUSPICIOUS = [
    'Department of Pathology, University Hospital Ghent, Belgium.',
    'Department of Pathology, GZA-ZNA Ziekenhuizen, Antwerp, Belgium',
    'Department of Pathology, Gustave Roussy, Grand Paris, France.',
    'Department of Pathology, GZA-ZNA Hospitals, Antwerp, Belgium',
    'Department of Medical Oncology, Gustave Roussy, Villejuif, France.',
    'Division of Molecular Pathology, The Netherlands Cancer Institute, '
    + 'Amsterdam, the Netherlands',
    'Department of Medical Oncology, Gustave Roussy, Villejuif, France.',
    'Division of Molecular Pathology, The Netherlands Cancer Institute, '
    + 'Amsterdam, the Netherlands'
]


def _get_suspiciously_similar_affiliations():
    unique_affiliations = list(set(
        [j.strip() for j in FULLDF.loc[:, 'affil']]))
    affilmap = dict()
    n1 = 15
    n2 = 5
    n3 = 5
    for saffil1 in unique_affiliations:
        affil1 = [j.strip() for j in saffil1.split(',')]
        for saffil2 in unique_affiliations:
            affil2 = [j.strip() for j in saffil2.split(',')]
            if saffil1 == saffil2:
                continue
            dept = affil1[0][:n1] == affil2[0][:n1]
            uni = affil1[1][:n2] == affil2[1][:n2]
            country = affil1[-1][:n3] == affil2[-1][:n3]
            if dept and uni and country and (
                    not any([
                        j.strip() in NOT_SUSPICIOUS for j in
                        (saffil1, saffil2)])
            ):
                # longer version is assumer to be more detailed (i.e better)
                if len(saffil1) > len(saffil2):
                    affilmap[saffil2] = saffil1
                else:
                    affilmap[saffil1] = saffil2

    if len(affilmap) > 0:
        print(
            "There are %d suspiciously similar affiliations that "
            "WILL BE MERGED:\n" % len(affilmap))
        for s1, s2 in affilmap.items():
            print(s1)
            print(s2, "\n")

    return affilmap


def _merge_affiliations():
    for a1, a2 in affilmap.items():
        FULLDF.loc[FULLDF.loc[:, "affil"] == a1, "affil"] = a2


affilmap = _get_suspiciously_similar_affiliations()
_merge_affiliations()

## Format combined author and member strings


# This assumes that if the same author has two or more affiliations, he/she
# appears in CONSECUTIVE ROWS in the dataframe

affil_no = dict()
done_auths = []
AUTHSTR = ""
AFFILSTR = ""

# name of first member
fmname = FULLDF.iloc[first_member, :]["auth"]

affid = 0

for _, row in FULLDF.iterrows():
    auth = row['auth']
    affil = row['affil']

    # make sure we know where to find this first_member
    if auth == fmname:
        fmloc = len(AUTHSTR)
        faloc = len(AFFILSTR)

    # add author to author string
    if auth not in done_auths:
        AUTHSTR += ', ' + auth
    else:
        AUTHSTR += '<sup>, </sup>'

    # add affiliation to this author
    affil_exists = affil not in affil_no.keys()
    fno = affid + 1 if affil_exists else affil_no[affil]
    AUTHSTR += "<sup>%d</sup>" % fno

    # add affiliation to affiliation string if not there
    if affil_exists:
        AFFILSTR += ", <sup>%d </sup>%s" % (fno, affil)

    # keep in memory
    done_auths.append(auth)
    affil_no[fno] = affil
    affid += 1

AUTHSTR = AUTHSTR[2:]
AFFILSTR = AFFILSTR[2:]

## Split author and member lists


PAPER_AUTHORS = AUTHSTR[:fmloc]
PAPER_AFFILS = AFFILSTR[:faloc]
WG_MEMBERS = AUTHSTR[fmloc:]
WG_AFFILS = AFFILSTR[faloc:]

# conform to journal style
PAPER_AUTHORS += \
    "International Immuno-Oncology Biomarker Working Group<sup>*</sup>"
PAPER_AFFILS += "<sup>* </sup>A full list of members and their affiliations" \
                + " is available at the end of the manuscript."

FINALSTR = "<b>Authors:</b>"
FINALSTR += '<br />'
FINALSTR += PAPER_AUTHORS
FINALSTR += '<br /> <br />'
FINALSTR += "<b>Affiliations:</b>"
FINALSTR += '<br />'
FINALSTR += PAPER_AFFILS
FINALSTR += '<br /> <br />'
FINALSTR += "<b>Working Group members:</b>"
FINALSTR += '<br />'
FINALSTR += WG_MEMBERS
FINALSTR += '<br /> <br />'
FINALSTR += "<b>Working Group affiliations:</b>"
FINALSTR += '<br />'
FINALSTR += WG_AFFILS

with open('./formatted_list.html', 'w') as f:
    f.write(FINALSTR)
