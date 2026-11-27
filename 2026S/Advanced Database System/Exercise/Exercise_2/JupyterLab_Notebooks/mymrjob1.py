
# This will create a local file to run your MapReduce program

from mrjob.job import MRJob
from mrjob.step import MRStep
from mrjob.util import log_to_stream
from mrjob.compat import jobconf_from_env
from mrjob.protocol import RawValueProtocol
from mr3px.csvprotocol import CsvProtocol
import csv
import io

import logging

# 
#  Below is the skeleton for a MapReduce program in mrjob.
#  Write your own solution here. Be sure that it actually runs successfully.


class MyMRJob1(MRJob):
    OUTPUT_PROTOCOL = RawValueProtocol

    POSTS_ID_INDEX = 0  # id
    POSTS_OWNER_INDEX = 13  # owneruserid
    POSTS_PARENT_INDEX = 14  # parentid
    POSTS_POST_TYPE_INDEX = 15  # posttypeid
    COMMENTS_POST_INDEX = 2  # postid
    COMMENTS_USER_INDEX = 5  # userid

    @classmethod
    def set_up_logging(cls, quiet=False, verbose=False, stream=None):
        log_to_stream(name='mrjob', debug=verbose, stream=stream)
        log_to_stream(name='__main__', debug=verbose, stream=stream)

    def mapper(self, _, line):
        row = next(csv.reader([line]))
        if row is None or (row[0] == "id"):
            return  # Skip unparseable lines and header lines

        # This script handles posts.csv
        if len(row) > 15:
            post_id = row[self.POSTS_ID_INDEX].split(".")[0]
            post_type = row[self.POSTS_POST_TYPE_INDEX].split(".")[0]
            owner_user_id = row[self.POSTS_OWNER_INDEX].split(".")[0]
            parent_id = row[self.POSTS_PARENT_INDEX].split(".")[0]

            # This is a question
            if post_type == "1":
                if post_id != "" and owner_user_id != "":
                    yield post_id, ("QUESTION", owner_user_id)\

            # This is an answer
            elif post_type == "2":
                if parent_id != "" and owner_user_id != "" and post_id != "":
                    yield parent_id, ("ANSWER", post_id, owner_user_id)

        # This script handles comments.csv
        else:
            answer_id = row[self.COMMENTS_POST_INDEX].split(".")[0]
            commenter_user_id = row[self.COMMENTS_USER_INDEX].split(".")[0]

            if answer_id != "" and commenter_user_id != "":
                yield answer_id, ("COMMENT", commenter_user_id)

    def reducer_prepare_answers(
        self,
        key,  # post_id (question_id or answer_id)
        values,
    ):

        question_owner = None
        answers = []
        comments = []

        for value in values:
            if value[0] == "QUESTION":  # key is question_id, value is question_owner
                question_owner = value[1]
            elif value[0] == "ANSWER":  # key is answer_id, value is answer_owner
                answer_id = value[1]  # for semantic meaning purposes, value[1] is answer_id
                answer_owner = value[2]
                answers.append((answer_id, answer_owner))
            elif value[0] == "COMMENT":  # key is answer_id, value is commenter_user_id
                comments.append(value[1])

        if question_owner and question_owner != "" and len(answers) > 0:
            for answer_id, answer_owner in answers:
                yield answer_id, ("QUESTION_ANSWER", question_owner, answer_owner)

        for commenter_user_id in comments:  # key is answer_id, value is commenter_user_id
            answer_id = key  # for semantic meaning purposes, key is answer_id
            if commenter_user_id and commenter_user_id != "":
                yield answer_id, ("COMMENTER", commenter_user_id)

    def reducer_emit_triples(self, answer_id, values):
        commenters = set()
        user_questioned = None
        user_answered = None

        for value in values:
            if value[0] == "QUESTION_ANSWER":
                user_questioned = value[1]
                user_answered = value[2]
            elif value[0] == "COMMENTER":
                commenters.add(value[1])

        if user_questioned and user_questioned != "" and user_answered and user_answered != "" and len(commenters) > 0:
            for commenter_user_id in commenters:            
                yield "ONE_KEY", f"{user_questioned},{user_answered},{commenter_user_id}"

    def reducer_sort(self, _, lines):
        all_rows = []
        for line in lines:    
            q, a, c = line.split(",")
            all_rows.append((int(q), int(a), int(c)))

        for line in sorted(all_rows):
            yield None, f"{line[0]},{line[1]},{line[2]}"

    def steps(self):
        return [
            MRStep(
                mapper=self.mapper,
                reducer=self.reducer_prepare_answers,
            ),
            MRStep(reducer=self.reducer_emit_triples),
            MRStep(reducer=self.reducer_sort),
        ]


if __name__ == "__main__":
    MyMRJob1.run()
