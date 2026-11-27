import pandas as pd
import numpy as np
import math
from scipy import sparse as sp
from scipy.sparse.linalg import norm
import sklearn.preprocessing as pp
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_X_y
from sklearn.utils import shuffle
#from numpy.core.umath_tests import inner1d
from sklearn.preprocessing import LabelBinarizer
from sklearn.metrics import mean_squared_error


def get_one_hot(targets):
    lb = pp.LabelBinarizer(sparse_output=True)
    lb.fit(targets.reshape(-1))
    return lb.transform(targets)


def to_Xy_format(R):
    n_users = R.shape[0]
    n_items = R.shape[1]

    users, items = R.nonzero()

    Xu = get_one_hot(users)
    Xi = get_one_hot(items)

    R = sp.csr_matrix(R)
    y = R.data
    X = sp.hstack([Xu, Xi])

    return X, y, n_users, n_items


def to_R_format(X, y, n_users, n_items):
    Xu = X.tocsc()[:, :n_users]
    Xi = X.tocsc()[:, n_users:]

    Xu = Xu.tocsr()
    Xi = Xi.tocsr()

    R_rec = sp.coo_matrix( (y, (Xu.indices, Xi.indices)), shape=(n_users, n_items) )

    return R_rec.tocsr()


def to_UI_arrays(X, n_users, n_items):
    Xu = X.tocsc()[:, :n_users]
    Xi = X.tocsc()[:, n_users:]

    U = Xu.argmax(axis=1).A1
    I = Xi.argmax(axis=1).A1

    return U, I




### https://stackoverflow.com/questions/38157972/how-to-implement-mini-batch-gradient-descent-in-python
def iterate_minibatches(inputs, targets, batchsize, shuffle=False):
    assert inputs.shape[0] == targets.shape[0]
    if shuffle:
        indices = np.arange(inputs.shape[0])
        np.random.shuffle(indices)
    for start_idx in range(0, inputs.shape[0], batchsize):
        end_idx = min(start_idx + batchsize, inputs.shape[0])
        if shuffle:
            excerpt = indices[start_idx:end_idx]
        else:
            excerpt = slice(start_idx, end_idx)
        yield inputs[excerpt], targets[excerpt]




VERBOSE = False

DEBUG = True


class Recommender_MF(BaseEstimator, RegressorMixin):



    def create_Ratings_Matrix(self):

        self.item_ids = self.ratings.item.unique()
        self.item_ids.sort()
        self.user_ids = self.ratings.user.unique()
        self.user_ids.sort()
        self.m = self.user_ids.size

        ## user_id and item_id are external ids; u_id and i_id are internal ids
        self.item_id_to_i_id = dict(zip(self.item_ids, range(0, self.item_ids.size)))
        self.i_id_to_item_id = dict(zip(range(0, self.item_ids.size), self.item_ids))

        self.user_id_to_u_id = dict(zip(self.user_ids, range(0, self.user_ids.size )))
        self.u_id_to_user_id = dict(zip(range(0, self.user_ids.size), self.user_ids))

        self.R = sp.csr_matrix((self.ratings.rating, (self.ratings.user.map(self.user_id_to_u_id), self.ratings.item.map(self.item_id_to_i_id))))


    def __init__(self, k = 5, eta = 0.002, lam = 0., n_epochs = 5, s_batch = 1, w_average = True, w_biases = True, rnd_mean = 0, rnd_std = 0.1):
        self.k = k
        self.eta = eta
        self.lam = lam
        self.n_epochs = n_epochs
        self.s_batch = s_batch
        self.w_average = w_average
        self.w_biases = w_biases
        self.rnd_mean = rnd_mean
        self.rnd_std = rnd_std



    def fit_init(self, X, y, n_users, n_items):
        X, y = check_X_y(X, y, accept_sparse=True)

        self.n_users_ = n_users
        self.n_items_ = n_items
        self.n_ratings_ = X.shape[0]

        self.X_ = X
        self.y_ = y


        ## USEFUL for debugging: remove randomness by fixing the random seed
        if DEBUG:
            np.random.seed(42)

        ########## BEGIN HERE ##########
        np.random.seed(1)

        # YOUR CODE HERE
        np.random.seed(42)  # TODO: remove
        self.mu_ = np.mean(self.y_)
        self.P_ = np.random.normal(self.rnd_mean, self.rnd_std, size=(self.n_users_, self.k))
        self.Q_ = np.random.normal(self.rnd_mean, self.rnd_std, size=(self.n_items_, self.k))
        self.bu_ = np.random.normal(self.rnd_mean, self.rnd_std, size=self.n_users_)
        self.bi_ = np.random.normal(self.rnd_mean, self.rnd_std, size=self.n_items_)
        # END YOUR CODE HERE

        ##########  END HERE  ##########

        # ## random shuffle the training data
        self.X_, self.y_ = shuffle(self.X_, self.y_)  # type: ignore

        return self

    def fit_sgd(self): ## stochastic gradient descent

        U, I = to_UI_arrays(self.X_, self.n_users_, self.n_items_)


        if VERBOSE:
            print("start of training")

        for epoch in range(self.n_epochs):

            epoch_loss = 0.

            for index in range(self.y_.shape[0]):  # type: ignore
                u = U[index]
                i = I[index]
                r_ui = self.y_[index]  # type: ignore

                ########## BEGIN HERE ##########

                # YOUR CODE HERE
                ### Compute the prediction for the user-item pair (u, i) using the current parameters ###
                if self.w_average and self.w_biases:
                    prediction = self.mu_ + self.bu_[u] + self.bi_[i] + self.P_[u].dot(self.Q_[i])
                elif self.w_average and not self.w_biases:
                    prediction = self.mu_ + self.P_[u].dot(self.Q_[i])
                elif not self.w_average and self.w_biases:
                    prediction = self.bu_[u] + self.bi_[i] + self.P_[u].dot(self.Q_[i])
                else:
                    prediction = self.P_[u].dot(self.Q_[i])

                ### Compute prediction error ###
                err = r_ui - prediction

                ### Perform a step of SGD to update the user and item feature vectors and biases (if enabled) based on the computed error ##
                # Compute delta_Pu and delta_Qi, the updates for the user and item feature vectors, respectively.
                delta_Pu = err * self.Q_[i] - self.lam * self.P_[u]
                delta_Qi = err * self.P_[u] - self.lam * self.Q_[i]

                # Update the user and item feature vectors
                self.P_[u] = self.P_[u] + self.eta * delta_Pu
                self.Q_[i] = self.Q_[i] + self.eta * delta_Qi
                if self.w_biases:
                    self.bu_[u] = self.bu_[u] + self.eta * (err - self.lam * self.bu_[u])
                    self.bi_[i] = self.bi_[i] + self.eta * (err - self.lam * self.bi_[i])

                # END YOUR CODE HERE
                
                ##########  END HERE  ##########

                epoch_loss += err * err


            ## epoch is done
            epoch_loss /= self.n_ratings_
            if VERBOSE:
                print(f'epoch {epoch} loss = {epoch_loss:.4f}')

        return self



    def fit_mgd(self): ## minibatch gradient descent, vectorized

        if VERBOSE:
            print("start training")

        print(self.n_users_, self.n_items_)
        print("X_", type(self.X_), self.X_.shape)
        print("y_", type(self.y_), self.y_.shape)

        print("self.P_", self.P_.shape)

        for epoch in range(self.n_epochs):

            epoch_loss = 0.

            for XB, yB in iterate_minibatches(self.X_, self.y_, self.s_batch):

                ########## BEGIN HERE ##########
                # YOUR CODE HERE
                ### Compute the predictions in vectorized form for the user-item pairs in the batch XB

                # Get the user and item indices for the user-item pairs in the batch XB
                X_U = XB[:, :self.n_users_]  # shape: (batch_size, n_users)
                X_I = XB[:, self.n_users_:]  # shape: (batch_size, n_items)

                # Get the user and item indices for the non-zero entries in X_U and X_I
                user_indices = X_U.nonzero()[1]  # shape: (batch_size,)
                item_indices = X_I.nonzero()[1]  # shape: (batch_size,)

                # Get the user and item feature vectors for the user-item pairs in the batch XB
                PB = self.P_[user_indices]  # shape: (batch_size, k)
                QB = self.Q_[item_indices]  # shape: (batch_size, k)

                dot_product = np.sum(PB * QB, axis=1)  # shape: (batch_size,)

                if self.w_average and self.w_biases:
                    predictions = (
                        self.mu_
                        + self.bu_[user_indices] 
                        + self.bi_[item_indices]
                        + dot_product
                    )
                elif self.w_average and not self.w_biases:
                    predictions = (
                        self.mu_
                        + dot_product
                    )
                elif not self.w_average and self.w_biases:
                    predictions = (
                        self.bu_[user_indices]
                        + self.bi_[item_indices]
                        + dot_product
                    )
                else:
                    predictions = dot_product  # shape: (batch_size,)

                ### Compute prediction errors ###
                errors = yB - predictions  # shape: (batch_size,)

                ### Perform a step of SGQ (vectorized) to update the user and item feature vectors and biases (if enabled) based on the computed errors ###

                # Accumulate updates for batch users/items
                # Use this as a user can have multiple ratings and an item can be rated by multiple users in the batch
                delta_PB = np.zeros_like(self.P_)
                delta_QB = np.zeros_like(self.Q_)

                np.add.at(delta_PB, user_indices, errors[:, np.newaxis] * QB - self.lam * PB)
                np.add.at(delta_QB, item_indices, errors[:, np.newaxis] * PB - self.lam * QB)

                # Update the user and item feature vectors
                self.P_ = self.P_ + self.eta * delta_PB
                self.Q_ = self.Q_ + self.eta * delta_QB
                if self.w_biases:
                    delta_buB = np.zeros_like(self.bu_)
                    delta_biB = np.zeros_like(self.bi_)

                    np.add.at(delta_buB, user_indices, errors - self.lam * self.bu_[user_indices])
                    np.add.at(delta_biB, item_indices, errors - self.lam * self.bi_[item_indices])

                    self.bu_[user_indices] = self.bu_[user_indices] + self.eta * delta_buB[user_indices]
                    self.bi_[item_indices] = self.bi_[item_indices] + self.eta * delta_biB[item_indices]

                ### Update epoch loss for a minibatch ###
                epoch_loss += np.sum(errors * errors)
                # END YOUR CODE HERE

                ##########  END HERE  ##########

            epoch_loss /= self.n_ratings_

            if VERBOSE:
                print(f'epoch {epoch} loss = {epoch_loss:.4f}')

        return self




    def fit(self, X, y, n_users, n_items):

        self.fit_init(X, y, n_users, n_items)

        if VERBOSE:
            print(self.get_params())

        if self.s_batch == 1: ## stochastic gradient descent
            self.fit_sgd()
        else: ## mini-batch stochastic gradient descent -- BONUS point
            self.fit_mgd()

        return self

    def predict(self, X, y=None): ### vectorized
        try:
            getattr(self, "n_users_")
        except AttributeError:
            raise RuntimeError("You must first train before predicting!")

        Xu = X.tocsc()[:, :self.n_users_]
        Xi = X.tocsc()[:, self.n_users_:]

        P_U = Xu.tocsr().dot(self.P_)
        Q_I = Xi.tocsr().dot(self.Q_)

        y_pred = (P_U * Q_I).sum(axis=1)

        if self.w_average:
            y_pred += self.mu_

        if self.w_biases:
            bu_U = Xu.tocsr().dot(self.bu_)
            bi_I = Xi.tocsr().dot(self.bi_)

            y_pred += bu_U + bi_I


        if y is not None:
            mse = mean_squared_error(y_pred, y)
            rmse = math.sqrt(mse)
            print(f'RMSE {rmse:.4f}')

        return y_pred

    def computeRMSE(self):
        y_pred = self.predict(self.X_)
        mse = mean_squared_error(y_pred, self.y_)
        rmse = math.sqrt(mse)
        return rmse, mse

    def score(self, X, y=None):
        if y is None:
            rmse, mse = self.computeRMSE()
            return -rmse
        else:
            y_pred = self.predict(X)
            mse = mean_squared_error(y_pred, y)
            return -math.sqrt(mse)


    def build_model(self, ratings, items_meta = None):
        self.ratings = ratings
        self.create_Ratings_Matrix()

        X, y, n_users, n_items = to_Xy_format(self.R)
        self.fit(X, y, n_users, n_items)


    def recommend(self, user_id, from_item_ids=None, topN=20):
        
        item_ids_rated_by_user_id = self.ratings[self.ratings['user']  == user_id]['item'].tolist()

        u_id = self.user_id_to_u_id[user_id]

        one_hot = np.zeros(self.n_users_)
        one_hot[u_id] = 1
        one_hot.reshape(1, -1)
        one_hot = sp.csr_matrix(one_hot)
        Xu = sp.csr_matrix(np.ones([self.n_items_,1])) * one_hot

        Xi = sp.diags(np.repeat(1, self.n_items_))

        X = sp.hstack([Xu, Xi])

        y_pred = self.predict(X)

        recommendations = []

        if from_item_ids is None:
            from_item_ids = self.item_ids

        for item_id in from_item_ids:
            if item_id in item_ids_rated_by_user_id:
                continue
            i_id = self.item_id_to_i_id[item_id]
            rating = y_pred[i_id]
            recommendations.append((item_id, rating))

        recommendations = sorted(recommendations, key=lambda x: -x[1])[:topN]
        
        return [int(item_id) for item_id, rating in recommendations]
