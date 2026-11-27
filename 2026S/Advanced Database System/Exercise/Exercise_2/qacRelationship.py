from mrjob.job import MRJob
from mrjob.step import MRStep
from mrjob.protocol import RawValueProtocol
from mrjob.compat import jobconf_from_env
import csv

class MRqacRelationship(MRJob):

    # Formats the output
    OUTPUT_PROTOCOL = RawValueProtocol

    # STAGE 1: Read all files and join Q with A
    def mapper_read_all(self, _, line):
        filename = jobconf_from_env("map.input.file")
        row = next(csv.reader([line]))

        # Ignore headers
        if row[0] == "id":
            return

        # Posts
        if "posts" in filename:
            post_id = row[0]
            owneruser_id = row[13].replace(".0", "")
            parent_id = row[14]
            posttype_id = row[15]
            
            # Question
            if posttype_id == "1":
                yield post_id, ("Q", owneruser_id)

            # Answer
            elif posttype_id == "2":
                yield parent_id, ("A", post_id, owneruser_id)

        # Comments
        elif "comments" in filename:
            commenter_user = row[5]
            post_id = row[2] 

            # Ignore comments without user
            if (commenter_user == None) or (commenter_user == ""):
                return

            yield post_id, ("C", commenter_user)


    def reducer_q_a_join(self, post_id, values):
        question_user = None
        answers = []
        comments = []

        for value in values:
            if value[0] == "Q":
                question_user = value[1]
            elif value[0] == "A":
                answer_id = value[1]
                answer_user = value[2]
                answers.append((answer_id, answer_user))
            elif value[0] == "C":
                commenter_user = value[1]
                comments.append(commenter_user)

        if question_user:
            for answer_id, answer_user in answers:
                yield answer_id, ("QA", question_user, answer_user)

        for c_user in comments:
            yield post_id, ("C", c_user)


    # STAGE 2: Join Questions, Answers with Comments
    def reducer_qa_c_join(self, post_id, values):
        qa = None
        commenters = set()

        for value in values:
            if value[0] == "QA":
                qa = (value[1], value[2]) # (question_user, answer_user)
            elif value[0] == "C":
                commenters.add(value[1]) # commenter_user

        if qa and commenters:
            question_user, answer_user = qa
            for commenter_user in commenters:
                yield None, f"({question_user}, {answer_user}, {commenter_user})"


    def steps(self):
        return [
            MRStep( mapper  = self.mapper_read_all,
                    reducer = self.reducer_q_a_join),
                    
            MRStep( reducer = self.reducer_qa_c_join)
        ]

if __name__ == '__main__':
    MRqacRelationship.run()