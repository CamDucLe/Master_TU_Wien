
# This will create a local file to run your MapReduce program

from mrjob.job import MRJob
from mrjob.protocol import RawValueProtocol
from mrjob.step import MRStep
from mrjob.util import log_to_stream
import csv
import heapq
import io


class MyMRJob2(MRJob):
    OUTPUT_PROTOCOL = RawValueProtocol

    TOP_K = 100

    POSTS_ID_INDEX = 0  # id
    POSTS_OWNER_INDEX = 13  # owneruserid
    POSTS_PARENT_INDEX = 14  # parentid
    POSTS_POST_TYPE_INDEX = 15  # posttypeid

    USER_ID_INDEX = 0  # id
    USERS_REPUTATION_INDEX = 7  # reputation
    USERS_DISPLAYNAME_INDEX = 3  # displayname

    @classmethod
    def set_up_logging(cls, quiet=False, verbose=False, stream=None):
        log_to_stream(name='mrjob', debug=verbose, stream=stream)
        log_to_stream(name='__main__', debug=verbose, stream=stream)

    def mapper(self, _, line):
        row = next(csv.reader([line]))
        if row is None or (row[0] == "id"):
            return  # Skip unparseable lines and header lines

        user_id = None
        post_type = None
        reputation = None
        displayname = None

        # This script handles posts.csv
        if len(row) > 15:
            user_id = row[self.POSTS_OWNER_INDEX].split(".")[0].strip()
            post_type = row[self.POSTS_POST_TYPE_INDEX].split(".")[0].strip()

            # To count number of questions/answers for each user
            if post_type == "1":
                yield user_id, ("POST_COUNTS", 1, 0)
            elif post_type == "2":
                yield user_id, ("POST_COUNTS", 0, 1)

        # This script handles users.csv
        else:
            user_id = row[self.USER_ID_INDEX].split(".")[0].strip()
            reputation = row[self.USERS_REPUTATION_INDEX].split(".")[0].strip()
            displayname = row[self.USERS_DISPLAYNAME_INDEX].strip()

            if reputation is None or reputation == "":
                reputation = 0

            if displayname is None or displayname == "":
                displayname = ""

            # To get each user's relevant information
            yield user_id, ("USER", displayname, reputation)


    def combiner(self, user_id, values):
        displayname = ""
        reputation = 0
        question_count = 0
        answer_count = 0

        for value in values:
            if value[0] == "POST_COUNTS":
                question_count += value[1]
                answer_count += value[2]
            elif value[0] == "USER":
                displayname = value[1]
                reputation += int(value[2])

        yield user_id, ("POST_COUNTS", question_count, answer_count)
        yield user_id, ("USER", displayname, reputation)

    def reducer(self, user_id, values):
        displayname = ""
        reputation = 0
        question_count = 0
        answer_count = 0

        for value in values:
            if value[0] == "POST_COUNTS":
                question_count += value[1]
                answer_count += value[2]
            elif value[0] == "USER":
                displayname = value[1]
                reputation += int(value[2])

        yield "ONE_KEY", (user_id, displayname, reputation, question_count, answer_count)

    def reducer_top_k(self, _, values):
        heap = []

        for user_id, displayname, reputation, question_count, answer_count in values:
            candidate = (reputation, user_id, displayname, question_count, answer_count)

            if len(heap) < self.TOP_K:
                heapq.heappush(heap, candidate)
            else:
                heapq.heappushpop(heap, candidate)

        top_users = sorted(heap, key=lambda item: (-item[0], item[1]))

        for reputation, user_id, displayname, question_count, answer_count in top_users:
            yield None, f"{displayname}, {reputation}, {question_count}, {answer_count}"

    def steps(self):
        return [
            MRStep(
                mapper=self.mapper,
                combiner=self.combiner,
                reducer=self.reducer,
            ),
            MRStep(
                reducer=self.reducer_top_k,
            ),
        ]


if __name__ == "__main__":
    MyMRJob2.run()
