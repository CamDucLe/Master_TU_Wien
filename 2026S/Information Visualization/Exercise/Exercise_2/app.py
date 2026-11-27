import pandas as pd
import json
from flask import Flask, render_template
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA


app = Flask(__name__)


### GLOBAL CONSTANTS ###

COUNTRIES = ['Afghanistan', 'Albania', 'Algeria', 'Angola', 'Argentina', 'Armenia', 'Australia',
             'Austria', 'Azerbaijan', 'Brazil', 'Bulgaria', 'Cameroon', 'Chile', 'China', 
             'Colombia', 'Croatia', 'Cuba', 'Cyprus', 'Czech Republic', 'Ecuador', 'Egypt, Arab Rep.',
             'Eritrea', 'Ethiopia', 'France', 'Germany', 'Ghana', 'Greece', 'India', 'Indonesia', 
             'Iran, Islamic Rep.', 'Iraq', 'Ireland', 'Italy', 'Japan', 'Jordan', 'Kazakhstan', 'Kenya',
             'Lebanon', 'Malta', 'Mexico', 'Morocco', 'Pakistan', 'Peru', 'Philippines', 'Russian Federation',
             'Syrian Arab Republic', 'Tunisia', 'Turkey', 'Ukraine']

NON_INDICATOR_COLS = {"Country", "Code", "Year"} # using a set for constant-time lookup with 'not in' 


#####################
###### Task 1 #######
#####################

def load_data(path: str) -> pd.DataFrame:
    """
    Loads and preprocesses the dataset.
    """
    df = pd.read_csv(path)
    df = df.rename(columns={"Name": "Country"})
    df = df[df["Country"].isin(COUNTRIES)].copy()
    df.sort_values(["Country", "Year"], inplace=True)
    return df


#####################
###### Task 2 #######
#####################

def compute_pca(df: pd.DataFrame, indicator_columns: list[str]) -> tuple:
    """
    Computes PCA on the most recent year data.
    """
    latest_year = int(df["Year"].max())
    df_latest = df[df["Year"] == latest_year].copy()
 
    X = df_latest[indicator_columns].apply(pd.to_numeric, errors="coerce")
    X_imputed = SimpleImputer(strategy="median").fit_transform(X)
    X_scaled = StandardScaler().fit_transform(X_imputed)
    X_pca = PCA(n_components=2).fit_transform(X_scaled)
 
    return df_latest, X_pca, latest_year


#####################
###### Task 3 #######
#####################

def build_pca_data(df_latest: pd.DataFrame, X_pca) -> list[dict]:
    """
    Formats the PCA data for the frontend scatterplot.js
    """
    return [
        {
            "name": row["Country"],
            "code": row["Code"],
            "x": float(X_pca[i, 0]),
            "y": float(X_pca[i, 1]),
        }
        for i, (_, row) in enumerate(df_latest.iterrows())
    ]


#####################
##### START UP ######
#####################

filtered_df = load_data("./data/agriRuralDevelopment_clean.csv")
 
indicator_columns = [c for c in filtered_df.columns if c not in NON_INDICATOR_COLS]
years = sorted(filtered_df["Year"].astype(int).unique().tolist())
 
df_latest, X_pca, most_recent_year = compute_pca(filtered_df, indicator_columns)
pca_data = build_pca_data(df_latest, X_pca)
json_data = json.loads(filtered_df.to_json(orient="records"))


#####################
####### FLASK #######
#####################

@app.route("/")
def home():
    return render_template(
        "index.html",
        data=json_data,
        pca_data=pca_data,
        indicators=indicator_columns,
        years=years,
        latest_year=most_recent_year,
    )


if __name__ == '__main__':
    app.run(debug=True)
