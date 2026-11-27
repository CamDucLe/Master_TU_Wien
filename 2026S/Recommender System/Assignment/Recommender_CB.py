import pandas as pd
import numpy as np
import scipy
from scipy import sparse as sp
import sklearn
import sklearn.preprocessing as pp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


class Recommender_CB:
      
    def __init__(self, profile_type='plot'):
        self.profile_type = profile_type
        
    def get_item_titles(self, item_ids):
        return [ self.items_meta[self.items_meta['item_id'] == id]['title'].item() for id in item_ids] 

    
    def build_item_contents(self):

        vectorizer = TfidfVectorizer(stop_words='english') # Define a TF-IDF Vectorizer that removes all english stop words (e.g., 'the', 'a')

        ### BEGIN SOLUTION

        # YOUR CODE HERE
        self.plot_tfidf = vectorizer.fit_transform(self.items_meta["plot"])
        self.plot_tfidf_tokens = vectorizer.get_feature_names_out()

        self.meta_tfidf = vectorizer.fit_transform(self.items_meta["metadata"])
        self.meta_tfidf_tokens = vectorizer.get_feature_names_out()
        # END YOUR CODE HERE
        
        self.plot_tfidf.sort_indices()
        self.meta_tfidf.sort_indices()
        
        self.set_content_type()

        ### END SOLUTION

    def set_content_type(self):
        if self.profile_type == 'plot':
            self.tfidf = self.plot_tfidf
            self.tfidf_tokens = self.plot_tfidf_tokens
        else:
            self.tfidf = self.meta_tfidf
            self.tfidf_tokens = self.meta_tfidf_tokens 
    
    
    def get_item_vectors(self, item_ids):
        i_ids = [self.i_id_to_item_id.index(item_id) for item_id in item_ids]
        item_vector = self.tfidf[i_ids]
        return item_vector 
    

    def get_user_profile(self, user_id, ratings):
        item_ids_rated_by_user_id = np.array( ratings.loc[ ratings['user'] == user_id ]['item'] )
        user_ratings = np.array( ratings.loc[ ratings['user'] == user_id ]['rating'] )

        ### BEGIN SOLUTION

        # YOUR CODE HERE
        # Get Compressed Sparse Row (CSR) matrix of the items rated by the user 
        item_vectors = self.get_item_vectors(item_ids_rated_by_user_id)  # shape: (n_items_rated_by_user_id, n_features)

        # Compute the weighted average of the item vectors, where the weights are the ratings given by the user
        weighted_item_vectors = item_vectors.multiply(user_ratings[:, np.newaxis])
        user_profile = np.asarray(weighted_item_vectors.sum(axis=0) / user_ratings.sum())
        # END YOUR CODE HERE

        user_profile = pp.normalize(user_profile)
        # print(user_profile.shape)
        # print(type(user_profile))

        ### END SOLUTION
        return user_profile    
    

    
    def build_user_profiles(self):
        positive_ratings = self.ratings[self.ratings['rating']>3]
        self.user_profiles = {}
        for user_id in positive_ratings['user'].unique():
            self.user_profiles[user_id] = self.get_user_profile(user_id, positive_ratings)
    
    
    
    def recommend(self, user_id, from_item_ids=None, topN=20):
        item_ids_rated_by_user_id = self.ratings.loc[ self.ratings['user'] == user_id ]['item'].tolist()


        if from_item_ids is None:
            from_item_ids = self.item_ids
                
        
        ### BEGIN SOLUTION

        # YOUR CODE HERE

        # 1. Retrieve the user profile
        user_profile = self.user_profiles[user_id].reshape(1, -1)

        # 2. Compute cosine similarity between user profile and each tf-idf vector of the items in from_item_ids
        sims = linear_kernel(user_profile, self.tfidf).flatten()

        # 3. Identify the indices in sims with highest similarity
        top_indices = sims.argsort()[::-1]

        # 4. Retrieve the item_ids from `self.i_id_to_item_id` that correspond to the indices found.
        item_ids = [self.i_id_to_item_id[i] for i in top_indices]

        # 5. Include in the recommendation list only items from `from_item_ids`, and exclude those in `item_ids_rated_by_user_id`.
        recommendations = [
            item_id
            for item_id in item_ids
            if item_id in from_item_ids and item_id not in item_ids_rated_by_user_id
        ]

        # 6. Return only the topN recommendations. Recommended items should be sorted from most similar to least similar.
        recommendations = recommendations[:topN]

        # END YOUR CODE HERE

        ### END SOLUTION
        return recommendations
    
    
    def in_rated(self, user_id, recommendations):
        item_ids_rated_by_user_id = self.ratings.loc[ self.ratings['user'] == user_id ]['item'].tolist()
        intersection = list(set(item_ids_rated_by_user_id) & set(recommendations))
        return len(intersection)>0
        
    
    def get_recommendation_score_dict(self, user_id, recommendations):
        user_profile = self.user_profiles[user_id]
        item_vectors = self.get_item_vectors(recommendations)
        scores = linear_kernel(item_vectors, user_profile).flatten()
        score_dict = dict(zip(recommendations, scores))
        return score_dict
  
    def get_recommendation_scores(self, user_id, recommendations):
        score_dict = self.get_recommendation_score_dict(user_id, recommendations)
        scores = [score_dict[item] for item in recommendations]
        return scores
  

    def build_model(self, ratings, items_meta):
        self.ratings = ratings
        self.items_meta = items_meta
        
        ## user_id and item_id are external ids; i_id is internal id
        self.item_ids = self.ratings.item.unique()
        self.item_ids.sort()
        
        self.user_ids = self.ratings.user.unique()
        self.user_ids.sort()
        
        self.i_id_to_item_id = self.items_meta['item_id'].tolist()
        
        self.build_item_contents()
        self.build_user_profiles()

