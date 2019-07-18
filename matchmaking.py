import csv
import re
from collections import defaultdict
import operator
datafilename = "matchmaking_responses.csv"

""" Matching parameters """
max_mentees_per_mentor = 2
min_mentees_per_mentor = 1


position_to_seniority = defaultdict(int)
position_to_seniority['senior academic'] = 4
position_to_seniority['postdoc researcher'] = 3
position_to_seniority['phd student'] = 2
position_to_seniority['masters student'] = 1
# the value 'industry' will get a seniority of 0. Industry mentors are matched to industry mentees



class Person:
    """ A person object represents a mentor or a mentee """

    def __init__(self,record,role):
        # initiate person based on the record in the csv from Google Forms

        self.role = role
        self.id = record[1]
        self.firstname = record[2]
        self.lastname = record[3]
        self.gender = record[5] # not used
        self.responded_position = record[9] # the literal response to the question 'what is your current status/position?'
        self.matched = False # set to true once the mentor or mentee has a final match

        if role == 'mentor':
            self.topics = record[6].split(', ')
        if role == 'mentee':
            self.topics = record[7].split(', ')
        self.experience = record[8]
        if re.match('.*(industr|engineer|manager|ceo ).*',record[9].lower()):
            # map 'industrial researcher', all engineers, manager, and CEO to industry
            self.position = 'industry'
        elif re.match('.*academic.*',record[9].lower()):
            self.position = 'senior academic'
        else:
            self.position = record[9].lower()

        self.region = record[10]
        self.seniority = position_to_seniority[self.position]
        self.matches = defaultdict(float) #keys are Pairs
        self.sorted_matches = list()

    def get_person_info(self):
        # for printing perposes
        return self.id, self.firstname, self.lastname,self.gender, self.topics, self.experience, self.position, self.seniority,self.region

    def sort_matches_by_score(self):
        # sort all potential matches
        self.sorted_matches = sorted(self.matches.items(),key=operator.itemgetter(1),reverse=True)


class Pair:
    def __init__(self,_mentor,_mentee):
        self.mentor = _mentor
        self.mentee = _mentee
        self.potential_match = self.is_potential_match()
        self.match_score = self.compute_total_score()
        self.final_match = False

    def overlap_topics(self):
        # how many of the mentee topics are covered by the mentor?
        topics_mentor = self.mentor.topics
        topics_mentee = self.mentee.topics
        overlap = 0
        for tmentee in topics_mentee:
            if tmentee in topics_mentor:
                overlap += 1
        #relative_overlap = float(overlap)/float(len(topics_mentee))
        # use absolute overlap because more topics should give more points to the match
        return overlap

    def mentor_more_senior(self):
        if self.mentor.seniority > self.mentee.seniority:
            return 1
        elif self.mentor.seniority == self.mentee.seniority == 4:
            # because senior academics could have another senior academic as mentor
            return 1
        else:
            return 0

    def both_industry(self):
        if self.mentor.position == self.mentee.position == 'industry':
            return 1
        else:
            return 0

    def both_academic(self):
        if self.mentor.position != 'industry' and self.mentee.position != 'industry':
            return 1
        else:
            return 0

    def region_match(self):
        if self.mentor.region == self.mentee.region:
            return 1
        else:
            return 0

    def is_potential_match(self):
        if self.both_industry() == 1 or (self.both_academic() and self.mentor_more_senior() > 0):
            return True
        else:
            return False

    def compute_total_score(self):
        match_score = self.mentor_more_senior()+self.both_industry()+self.region_match()+self.overlap_topics()
        return match_score


""" Read the csv file downloaded from Google forms """
""" It might be needed to first save it as UTF-8 locally """

mentors = list()
mentees = list()
with open(datafilename, 'r',encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile, delimiter=',', quotechar='\"')
    headers = next(reader)
    response_id = 0
    for row in reader:
        #print(row)
        response_id += 1
        if 'advisee' in row[4]:
            mentee = Person(row,'mentee')
            mentees.append(mentee)
        elif 'advisor' in row[4]:
            mentor = Person(row,'mentor')
            mentors.append(mentor)

csvfile.close()

""" Find potential matches per mentee; then score and rank each match """

number_of_mentees_per_mentor = defaultdict(int)

for mentee in mentees:
    max_score_for_this_mentee = 0
    for mentor in mentors:
        potential_pair = Pair(mentor,mentee)
        if potential_pair.potential_match:
            mentee.matches[potential_pair] = potential_pair.match_score
            mentor.matches[potential_pair] = potential_pair.match_score
            if potential_pair.match_score > max_score_for_this_mentee:
                max_score_for_this_mentee = potential_pair.match_score

    """ Function that sets the list of ranked matches in the person object """
    mentee.sort_matches_by_score()

    get_next_mentor_in_rank = True
    while get_next_mentor_in_rank and len(mentee.sorted_matches) > 0:
        (next_pair_in_line,max_score) =  mentee.sorted_matches[0]

        """ Find the highest score among the available mentors (that is the score of the mentor in rank 1)"""
        i = 0
        preferred_mentor = None
        for (potential_pair,score) in mentee.sorted_matches:

            potential_mentor = potential_pair.mentor
            if score >= max_score and number_of_mentees_per_mentor[potential_mentor.id] < min_mentees_per_mentor:
                """ try to find a mentor that has fewer than the minimum number of mentees and the maximum matching score"""
                (preferred_pair, score) = mentee.sorted_matches.pop(i)
                preferred_mentor = preferred_pair.mentor
                preferred_pair.final_match = True
                mentee.matched = True
                preferred_mentor.matched = True
                number_of_mentees_per_mentor[preferred_mentor.id] += 1
                get_next_mentor_in_rank = False
                break
            i += 1

        if preferred_mentor is None:
            """ If there is no mentor that has fewer than the minimum number of mentees and the maximum matching score,
            get the first mentor with the maximum matching score that does not yet have the maximum number of mentees """
            (next_pair_in_line, max_score) = mentee.sorted_matches.pop(0)

            if number_of_mentees_per_mentor[next_pair_in_line.mentor.id] < max_mentees_per_mentor:
                next_pair_in_line.final_match = True
                mentee.matched = True
                next_pair_in_line.mentor.matched = True
                number_of_mentees_per_mentor[next_pair_in_line.mentor.id] += 1
                get_next_mentor_in_rank = False

    if len(mentee.sorted_matches) <= 0:
        print("-> NO MATCH") # this should never happen


""" Print all matches """

print("\nNumber of mentors:",len(mentors))
print("Number of mentees:",len(mentees))


print("\nMatching score\tMentor\t\tE-mail address\tPosition\tRegion\tTopics\tMentee\t   \tE-mail address\tPosition\tRegion\tTopics")
for mentor in mentors:

    for pair in mentor.matches:
        if pair.final_match:
            name_mentor = mentor.firstname+"\t"+mentor.lastname
            mentee = pair.mentee
            name_mentee = mentee.firstname+"\t"+mentee.lastname
            print(pair.match_score,name_mentor,mentor.id,mentor.responded_position,mentor.region,mentor.topics,name_mentee,mentee.id,mentee.responded_position,mentee.region,mentee.topics,sep="\t")

print("\nMentees without mentor")

for mentee in mentees:
    if not mentee.matched:
        print(mentee.get_person_info())

print("\nMentors without mentee")

for mentor in mentors:
    if not mentor.matched:
        print(mentor.get_person_info())

