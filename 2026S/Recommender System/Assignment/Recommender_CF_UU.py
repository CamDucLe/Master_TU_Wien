import pandas as pd
import numpy as np
from scipy import sparse as sp
from scipy.sparse.linalg import norm
import sklearn.preprocessing as pp


class Recommender_CF_UU:
    UU = {} ## user-user similarities; constructed lazily

    def create_Ratings_Matrix(self):

        self.item_ids = self.ratings['item'].unique()
        self.item_ids.sort()
        self.user_ids = self.ratings['user'].unique()
        self.user_ids.sort()
        self.m = self.user_ids.size

        ## user_id and item_id are external ids; u_id and i_id are internal ids
        self.item_id_to_i_id = dict(zip(self.item_ids, range(0, self.item_ids.size)))
        self.i_id_to_item_id = dict(zip(range(0, self.item_ids.size), self.item_ids))

        self.user_id_to_u_id = dict(zip(self.user_ids, range(0, self.user_ids.size )))
        self.u_id_to_user_id = dict(zip(range(0, self.user_ids.size), self.user_ids))

        self.R = sp.csr_matrix((self.ratings['rating'], (self.ratings['user'].map(self.user_id_to_u_id), self.ratings['item'].map(self.item_id_to_i_id))))
        self.R_dok = self.R.todok()


    def compute_user_avgs(self):
        user_sums = self.R.sum(axis=1).A1 ## matrix converted to 1-D array via .A1
        self.user_cnts = (self.R != 0).sum(axis=1).A1
        self.user_avgs = user_sums / self.user_cnts

    def compute_pairwise_user_similarity(self, u_id, v_id):

        u = self.R[u_id,:].copy()
        v = self.R[v_id,:].copy()

        ### BEGIN SOLUTION

        # YOUR CODE HERE
        # Get the mean rating of 2 users
        ru_mean = self.user_avgs[u_id]
        rv_mean = self.user_avgs[v_id]

        # Calculate mean-centered rating
        u.data -= ru_mean
        v.data -= rv_mean

        # Get common items
        Iu_Iv = u.multiply(v)

        # Calculate norm (consider set of items rated by user only)
        u_norm = float(np.sqrt(u.multiply(u).sum()))
        v_norm = float(np.sqrt(v.multiply(v).sum()))

        # Calculate numerator and denominator
        denominator = u_norm * v_norm
        if Iu_Iv.data.size > 0:
            numerator = float(Iu_Iv.data.sum())
        else:
            numerator = 0.0
        
        if denominator == 0:
            similarity = 0.
        else:
            similarity = numerator/denominator

        # END YOUR CODE HERE

        ### END SOLUTION
        return similarity

    def compute_user_similarities(self, u_id):
        if u_id in self.UU.keys(): ## persist
            return self.UU[u_id]

        uU = np.empty((self.m,))

        
        
        ########## BEGIN HERE ##########
        
        
        


        ##########  END HERE  ##########
        
        
        #Add the version without the for loop here if you have done it
        # """
        ########## BEGIN BONUS ##########

        # YOUR CODE HERE
        # Copy original matrix to make it mean-centered and normalized
        R_copy = self.R.copy()

        ### Mean-centered (With the help of Copilot) ###
        # Find the number of items that each user rated (number of non-zero entries)
        n_non_zero_each_row = np.diff(R_copy.indptr)  # I_u
        # Repeat the average rating of each user by the number of items they rated
        mean_ratings = np.repeat(
            a=self.user_avgs,
            repeats=n_non_zero_each_row,
            axis=None,
        )  # 1-D array; array size = R.data
        # Get mean-centered data
        R_copy.data -= mean_ratings

        ### Normalize each row ###
        # Calculate norm of each row
        each_row_norm = np.sqrt(R_copy.multiply(R_copy).sum(axis=1)).A1  # 1-D array with shape = (m,)
        each_row_norm[each_row_norm == 0] = 1  # avoid division by zero
        # Cast type to float before division (float64 because float32 may not correct due to precision - tested)
        R_copy = R_copy.astype(np.float64)
        # Repeat the norm of each row by the number of items rated of the corresponding user
        row_norms = np.repeat(
            a=each_row_norm,
            repeats=n_non_zero_each_row,
            axis=None,
        )  # 1-D array; array size = R.data
        # Normalize data
        R_copy.data /= row_norms

        ### Compute similarities using dot product ###
        u = R_copy[u_id, :].copy()
        uU = R_copy.dot(u.T).toarray().ravel()  # numpy array

        # END YOUR CODE HERE
        
        #########  END BONUS  ##########

        self.UU[u_id] = uU

        return self.UU[u_id]


    def create_user_neighborhood(self, u_id, i_id):
        nh = {} ## the neighborhood dict with (user id: similarity) entries
        ## nh should not contain u_id and only include users that have rated i_id; there should be at most k neighbors
        self.compute_user_similarities(u_id)
        uU = self.UU[u_id].copy()

        uU_copy = uU.copy() ## so that we can modify it, but also keep the original


        ########## BEGIN HERE ##########

        # YOUR CODE HERE
        # Get users (except u_id) who rated item i_id
        n_users = uU_copy.shape[0]
        users_rated_item_i = [v_id for v_id in range(n_users) if v_id != u_id and (v_id, i_id) in self.R_dok]
        if len(users_rated_item_i) == 0:
            return nh

        # Get the similarities between user u_id vs users who rated item i_id
        uU_rated = uU_copy[users_rated_item_i].copy() # 1-D array size (|N_u|,)

        # Zip users'id, who rated_item_i, and  similarity of u_id and that user to sort and get top-k
        neighborhood_with_sim = list(zip(users_rated_item_i, uU_rated))

        # Sort by absolute similarity or normal similarity
        if self.with_abs_sim:
            neighborhood_with_sim.sort(key=lambda x: abs(x[1]), reverse=True)
        else:
            neighborhood_with_sim.sort(key=lambda x: x[1], reverse=True)

        # Get top-k most similar users
        neighborhood_with_sim = neighborhood_with_sim[:self.k]

        # Sort by user's (v_id) to make return dict cleaner and match with expected output (in the same order also)
        neighborhood_with_sim.sort(key=lambda x: x[0], reverse=False)

        # Form result: v_id: sim(u_id, v_id)
        nh = {v_id: sim_u_v for v_id, sim_u_v in neighborhood_with_sim}

        ##########  END HERE  ##########
        
        return nh


    def predict_rating(self, u_id, i_id):

        # if (u_id, i_id) in self.R_dok:
        #     print("user", u_id, "has rated item", i_id, "with", self.R[u_id, i_id])
        # else:
        #     print("user", u_id, "has not rated item", i_id)
        # print("k:", self.k, "with_deviations:", self.with_deviations, "with_abs_sim:", self.with_abs_sim)

        nh = self.create_user_neighborhood(u_id, i_id)

        neighborhood_weighted_avg = 0.

        ########## BEGIN HERE ##########

        # YOUR CODE HERE
        # Get similarities and user's id from user_neighborhood
        w_uv = np.array([nh[key] for key in nh.keys()])  # 1-D array size (|N_u|,)
        v_id_list = list(nh.keys())

        # Get ratings of top-k selected users who rated item i_id then convert from csr_matrix to 1-D numpy array
        R_vi = self.R[v_id_list, i_id].copy()
        R_vi = R_vi.toarray().flatten()  # 1-D array size (|N_u|,)

        # Get the average rating of each user who rated item i_id
        user_avgs_vi = self.user_avgs[v_id_list].copy()  # 1-D array size (|N_u|,)

        # Calculate denominator and nominator
        denominator = sum(np.absolute(w_uv))
        if self.with_deviations:
            nominator = (w_uv * (R_vi - user_avgs_vi)).sum()
        else:
            nominator = (w_uv * R_vi).sum()

        if denominator == 0. or len(nh) == 0:
            neighborhood_weighted_avg = 0.
        else:
            neighborhood_weighted_avg = nominator / denominator
        
        if self.with_deviations:
            prediction = self.user_avgs[u_id] + neighborhood_weighted_avg
            # print(f'prediction {prediction:.4f} (user_avg {self.user_avgs[u_id]:.4f} offset {neighborhood_weighted_avg:.4f})')
        else:
            prediction = neighborhood_weighted_avg
            # print(f'prediction {prediction:.4f} (user_avg {self.user_avgs[u_id]:.4f})')
        
        ##########  END HERE  ##########


#         if sum_weights != 0: ## avoid division by zero
#             neighborhood_weighted_avg = sum_scores/sum_weights


#         if self.with_deviations:
#             prediction = self.user_avgs[u_id] + neighborhood_weighted_avg
# #             print(f'prediction {prediction:.4f} (user_avg {self.user_avgs[u_id]:.4f} offset {neighborhood_weighted_avg:.4f})')
#         else:
#             prediction = neighborhood_weighted_avg
# #             print(f'prediction {prediction:.4f} (user_avg {self.user_avgs[u_id]:.4f})')

        return prediction


    def __init__(self, with_abs_sim = True, with_deviations = True, k = 50):
        self.with_abs_sim = with_abs_sim
        self.with_deviations= with_deviations
        self.k = k
        self.UU = {}


    def build_model(self, ratings, items_meta = None):
        self.ratings = ratings
        self.UU = {}

        self.create_Ratings_Matrix()
        self.compute_user_avgs()


    def recommend(self, user_id, from_item_ids=None, topN=20):

        item_ids_rated_by_user_id = self.ratings[self.ratings['user'] == user_id]['item'].tolist()

        u_id = self.user_id_to_u_id[user_id]

        recommendations = []

        if from_item_ids is None:
            from_item_ids = self.item_ids

        for item_id in from_item_ids:
            if item_id in item_ids_rated_by_user_id:
                continue
            i_id = self.item_id_to_i_id[item_id]
            rating = self.predict_rating(u_id, i_id)
            recommendations.append((item_id, rating))

        recommendations = sorted(recommendations, key=lambda x: -x[1])[:topN]

        return [int(item_id) for item_id, rating in recommendations]
