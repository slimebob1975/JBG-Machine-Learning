import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix

class DarkNumberCalculator:

    # 299o, JBG v1.1 (agreed 2026-11-16, DN-01 F1/F2 and the bounds on c): a
    # correction of the standard method that leaves D unchanged in every
    # normal case. D (and c) are -1, "undefined", when
    #   - a rate is undefined: no rows outside the target (TN + FP = 0) or no
    #     target rows (TP + FN = 0) in the scope (also a one-label scope);
    #   - c could not be estimated, or lies outside [CORRECTION_MIN,
    #     CORRECTION_MAX]: the pipeline is ill-suited to the problem.
    # With no false positives and rows outside the target, D = 0 whatever c is.
    METHOD_VERSION = "1.3"               # 299u: the agreed reading; 300l: c = c_in / c_unseen
    # 299u, JBG v1.2 (settled 2026-11-16): D estimates the hidden share H, the
    # share of the rows registered as not T that really are T, so it is capped
    # at 1 (with a flag: the estimate has broken down there).
    CAP = 1.0
    UNDEFINED = -1.0
    CORRECTION_MIN = 1.0
    CORRECTION_MAX = 10.0
    # 299q/299q2, JBG v1.1 (DN-01 F4, settled 2026-11-16): a correction model is
    # taken to memorise its training rows (c may then be overestimated; a
    # warning, D is unchanged) when its fit to them in the flip test is at least
    # MEMORISATION_FIT and exceeds its accuracy on unseen rows (the cross-trained
    # model's test part) by at least MEMORISATION_GAP. An easy problem gives
    # high values for both and is not flagged. Without an unseen accuracy, only
    # the fit can be judged: MEMORISATION_THRESHOLD (299q's rule).
    # 299s, JBG v1.1 (DN-01 F6, settled 2026-11-16, option A1): the flip test's
    # folds and repeats, independent of the computer's CPU count.
    FLIP_TEST_FOLDS = 4
    FLIP_TEST_REPEATS = 2
    MEMORISATION_FIT = 0.95
    MEMORISATION_GAP = 0.05
    MEMORISATION_THRESHOLD = 0.99

    @classmethod
    def memorises(cls, fit, unseen=None) -> bool:
        """299q2: whether a correction model with this training fit (and accuracy
        on unseen rows, if known) is taken to memorise its training rows."""
        try:
            fit = float(fit)
        except (TypeError, ValueError):
            return False
        if fit != fit:
            return False
        try:
            unseen = float(unseen)
        except (TypeError, ValueError):
            unseen = None
        if unseen is None or unseen != unseen:
            return fit >= cls.MEMORISATION_THRESHOLD
        return fit >= cls.MEMORISATION_FIT and fit - unseen >= cls.MEMORISATION_GAP

    @classmethod
    def bounded_correction(cls, corr, source: str):
        """(c, source) with v1.1's bounds: an unestimable or out-of-bounds c is -1."""
        if "unestimable" in str(source):
            return cls.UNDEFINED, "undefined/unestimable"
        try:
            value = float(corr)
        except (TypeError, ValueError):
            return cls.UNDEFINED, "undefined/unestimable"
        if not (cls.CORRECTION_MIN <= value <= cls.CORRECTION_MAX):
            return cls.UNDEFINED, f"undefined/out_of_bounds ({source})"
        return value, source

    @staticmethod
    def target_vs_rest_certainty(class_probabilities, target, predicted_binary, fallback):
        """299t, JBG v1.1 (DN-01 F7, settled 2026-11-16, reading 1): the certainty
        behind each verdict for one target, target against the rest: P(target) on
        rows predicted as the target and 1 - P(target) on the others. It was the
        probability of the predicted label only, which with more than two classes
        is less than the certainty that a row is not the target (the rest's
        probability is split between the other classes). Two classes: the same
        values. Without class probabilities (direct calls), the old values."""
        if class_probabilities is None or target not in getattr(class_probabilities, "columns", ()):
            return fallback
        p_target = pd.Series(class_probabilities[target].to_numpy(dtype=float),
                             index=predicted_binary.index)
        return p_target.where(predicted_binary == 1, 1.0 - p_target)

    @staticmethod
    def _counts(real: pd.Series, predicted: pd.Series):
        """TN, FP, FN, TP for target (1) against the rest (0), also for a scope
        with one label only (299o, DN-01 F2: it raised)."""
        return confusion_matrix(real, predicted, labels=[0, 1]).ravel()

    @classmethod
    def _undefined(cls, TN, FP, FN, TP, corr) -> bool:
        """299o: whether D is undefined (-1) for these counts and this c."""
        if TN + FP == 0 or TP + FN == 0:
            return True                          # a rate is undefined
        if FP == 0:
            return False                         # D = 0 whatever c is
        return corr == cls.UNDEFINED

    FORMULA_LATEX = {
        "base": r"D = c\,(1 - TN_r)\,(2 - TP_r)",
        "single_alpha": r"D = c\,\alpha\,(1 - TN_r)\,(2 - TP_r)",
        "separated_alpha": r"D = c\,\alpha_{FP}\,(1 - TN_r)\,(1 + \alpha_{FN}\,(1 - TP_r))",
        "non_linear": r"D = c\,(1 - TN_r^{1/k})\,(2 - TP_r^{1/k})",
        "non_linear_alpha": r"D = c\,\alpha\,(1 - TN_r^{1/k})\,(2 - TP_r^{1/k})",
    }

    FORMULA_ALPHA_NOTES = {
        "base": "No alpha",
        "single_alpha": "alpha: mean certainty on errors",
        "separated_alpha": "alpha_FP / alpha_FN: mean certainty on FP / FN (alpha_FN weighs the misses only)",
        "non_linear": "No alpha",
        "non_linear_alpha": "alpha: mean certainty on errors",
    }

    @classmethod
    def resolve_calculation_type(cls, method, alpha) -> str:
        """Resolve the GUI/config Method + Alpha choice to the implemented calculator branch."""
        method_name = getattr(method, "name", method)
        alpha_name = getattr(alpha, "name", alpha)
        method_name = str(method_name).strip().upper()
        alpha_name = str(alpha_name).strip().upper()
        calculation_types = {
            ("LINEAR", "NONE"): "base",
            ("LINEAR", "SINGLE"): "single_alpha",
            ("LINEAR", "SEPARATED"): "separated_alpha",
            ("NON_LINEAR", "NONE"): "non_linear",
            ("NON_LINEAR", "SINGLE"): "non_linear_alpha",
        }
        try:
            return calculation_types[(method_name, alpha_name)]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported Dark Number method/alpha combination: {method_name}/{alpha_name}"
            ) from exc

    @classmethod
    def get_formula_spec(cls, method, alpha, root_degree: int = 3) -> dict:
        """Return display metadata for the exact calculator branch selected by Method + Alpha."""
        calculation_type = cls.resolve_calculation_type(method, alpha)
        latex = cls.FORMULA_LATEX[calculation_type].replace("1/k", f"1/{int(root_degree)}")
        return {
            "calculation_type": calculation_type,
            "latex": latex,
            "alpha_note": cls.FORMULA_ALPHA_NOTES[calculation_type],
            "root_degree": int(root_degree),
        }

    def __init__(self):
        pass

    @classmethod
    def correction_is_unused(cls, real, predicted, probabilities, target, calculation_type):
        """Prove the zero-FP multiplier is zero on a valid reported scope.

        No observed negatives is not zero FPR: the historical rate is undefined
        there. Require both target/rest support, aligned complete labels and valid
        confidence values for alpha formulas before skipping any correction work.
        """
        if calculation_type != "all" and calculation_type not in cls.FORMULA_LATEX:
            return False
        if (len(real) == 0 or not real.index.equals(predicted.index)
                or real.isna().any() or predicted.isna().any()):
            return False
        target_rows = real == target
        if not target_rows.any() or target_rows.all():
            return False
        if ((~target_rows) & (predicted == target)).any():
            return False
        uses_alpha = calculation_type in {"all", "single_alpha", "separated_alpha", "non_linear_alpha"}
        if uses_alpha and (
            probabilities is None or not real.index.equals(probabilities.index)
            or probabilities.isna().any() or not probabilities.between(0, 1).all()
        ):
            return False
        return True

    def compute_posneg_rates(self, TN: int, FP: int, FN: int, TP: int):

        # Compute performance rates
        TNr = TN / (TN + FP) if (TN + FP) > 0 else -1
        TPr = TP / (TP + FN) if (TP + FN) > 0 else -1

        return TPr, TNr

    def compute_dark_number(self, real: pd.Series, predicted: pd.Series, corr: float = 1.0):
        
        # Compute confusion matrix elements
        TN, FP, FN, TP = self._counts(real, predicted)
        if self._undefined(TN, FP, FN, TP, corr):
            return self.UNDEFINED                  # 299o: undefined
        if FP == 0:
            corr = 1.0                           # 299o: D = 0, c does not matter
        
        # Computes rates
        TPr, TNr = self.compute_posneg_rates(TN, FP, FN, TP)

        # Calculate dark number using no alpha correction
        dark_number =  corr * (1 - TNr) * (2 - TPr)
        
        return dark_number

    # Compute dark number based on one single alpha value
    def compute_dark_number_single_alpha(self, real: pd.Series, predicted: pd.Series, pred_prob: pd.Series, corr: float = 1.0):
        
        # Compute confusion matrix elements
        TN, FP, FN, TP = self._counts(real, predicted)
        if self._undefined(TN, FP, FN, TP, corr):
            return 1.0, self.UNDEFINED                  # 299o: undefined
        if FP == 0:
            corr = 1.0                           # 299o: D = 0, c does not matter
        
        # Computes rates
        TPr, TNr = self.compute_posneg_rates(TN, FP, FN, TP)

        # Compute the mean certainty of the predictions where real and predicted differ
        alpha = pred_prob[real != predicted].mean() if (FP + FN > 0) else 1
        
        # Calculate dark number using single alpha correction
        dark_number = corr * alpha * (1 - TNr) * (2 - TPr)
        
        return alpha, dark_number

    # Compute dark number based on two alpha values

    def compute_dark_number_separated_alpha(self, real: pd.Series, predicted: pd.Series, pred_prob: pd.Series, corr: float = 1.0):
        
        # Compute confusion matrix elements
        TN, FP, FN, TP = self._counts(real, predicted)
        if self._undefined(TN, FP, FN, TP, corr):
            return [1.0, 1.0], self.UNDEFINED                  # 299o: undefined
        if FP == 0:
            corr = 1.0                           # 299o: D = 0, c does not matter
        
        # Computes rates
        TPr, TNr = self.compute_posneg_rates(TN, FP, FN, TP)

        # Compute mean certainty for FP and FN
        alpha_FP = pred_prob[(real == 0) & (predicted == 1)].mean() if FP > 0 else 1
        alpha_FN = pred_prob[(real == 1) & (predicted == 0)].mean() if FN > 0 else 1

        # Calculate dark number using separated alpha correction
        # 299u, JBG v1.2 (settled 2026-11-16): soft counting. alpha_FN weighs the
        # misses only, 1 + alpha_FN * (1 - TP_r); it multiplied the whole factor
        # (2 - TP_r), so with no misses a low alpha_FN still pulled D down.
        dark_number = corr * alpha_FP * (1 - TNr) * (1 + alpha_FN * (1 - TPr))
        
        return [alpha_FP, alpha_FN], dark_number

    # Compute dark number with non-linear scaling
    def compute_dark_number_non_linear(self, real: pd.Series, predicted: pd.Series, pred_prob: pd.Series,  \
                                    use_alpha=False,  root_degree: int=3, corr: float = 1.0):
        
        # Compute confusion matrix elements
        TN, FP, FN, TP = self._counts(real, predicted)
        if self._undefined(TN, FP, FN, TP, corr):
            return 1.0, self.UNDEFINED                  # 299o: undefined
        if FP == 0:
            corr = 1.0                           # 299o: D = 0, c does not matter
        
        # Computes rates
        TPr, TNr = self.compute_posneg_rates(TN, FP, FN, TP)

        # Alpha calculation where real and predicted differs
        if use_alpha:
            alpha = pred_prob[real != predicted].mean() if (FP + FN > 0) else 1
        else:
            alpha = 1.0

        # Calculate dark number using non-linear scaling
        dark_number = corr * alpha * (1 - TNr**(1 / root_degree)) * (2 - TPr**(1 / root_degree))
        
        return alpha if use_alpha else 1.0, dark_number

    # Unified interface for calculating dark numbers
    def compute_dark_numbers(self, real_target: pd.Series, pred_target: pd.Series, prob_pred: pd.Series, \
                            type="base", root_degree=3, corrs=None, targets=None,
                            class_probabilities=None):
        """
        corrs should be a dictionary with correction factors for each class in real_target 
        """

        # This DataFrame will hold the results
        dark_numbers = pd.DataFrame(columns=["type", "target", "alphas", "corr", "dark_number",
                                             "capped"])

        # What types of dark numbers to consider?
        if type == "all":
            types = ["base", "single_alpha", "separated_alpha", "non_linear", "non_linear_alpha"]
        else:
            types = [type]

        selected_targets = list(real_target.unique()) if targets is None else list(targets)
        available_targets = set(real_target.unique())
        missing_targets = [target for target in selected_targets if target not in available_targets]
        if missing_targets:
            raise ValueError(f"Dark Number target(s) not present in data: {missing_targets}")

        # Compute dark number for each type
        for type in types:
        
        # Compute dark number for each target in the classification
            for target in selected_targets:
                
                try:
                    corr = corrs[target]
                except:
                    print(f"[WARNING] No correction factor for target {target} available. Using fallback 1.0.")
                    corr = 1.0

                # Convert to binary classification 
                real_target_bin = pd.Series(real_target.apply(func=(lambda x: 1 if x == target else 0)), name="real_target")
                pred_target_bin = pd.Series(pred_target.apply(func=(lambda x: 1 if x == target else 0)), name="pred_target")
                alpha_prob = self.target_vs_rest_certainty(
                    class_probabilities, target, pred_target_bin, prob_pred)       # 299t

                if type == "base":
                    dark_number = self.compute_dark_number(real_target_bin, pred_target_bin, corr)
                    alpha = 1.0   
                elif type == "single_alpha":
                    alpha, dark_number = self.compute_dark_number_single_alpha(real_target_bin, pred_target_bin, alpha_prob, corr)
                elif type == "separated_alpha":
                    alpha, dark_number = self.compute_dark_number_separated_alpha(real_target_bin, pred_target_bin, alpha_prob, corr)
                elif type == "non_linear":
                    alpha, dark_number = self.compute_dark_number_non_linear(real_target_bin, pred_target_bin, alpha_prob, \
                                                                use_alpha=False, root_degree=root_degree, corr=corr)
                elif type == "non_linear_alpha":
                    alpha, dark_number = self.compute_dark_number_non_linear(real_target_bin, pred_target_bin, alpha_prob, \
                                                                use_alpha=True, root_degree=root_degree, corr=corr)
                else:
                    raise ValueError(f"The type of dark number is not supported: {type}")
                
                # 299u, JBG v1.2: capped at 1, with a flag.
                capped = dark_number != self.UNDEFINED and dark_number > self.CAP
                if capped:
                    dark_number = self.CAP
                row = {"type": type, "target": target, "alphas": alpha, "corr": corr,
                       "dark_number": dark_number, "capped": bool(capped)}
                dark_numbers.loc[len(dark_numbers)] = row
            
        return dark_numbers

def main():
    
    print("Dark number computations")

    # Load the iris dataset
    data = load_iris()
    X = data.data
    y = data.target

    # Split into train and test datasets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train a logistic regression model
    model = LogisticRegression(max_iter=200)
    model.fit(X_train, y_train)
    accuracy = model.score(X_train, y_train)
    print(f"Train accuracy: {accuracy}")
    accuracy = model.score(X_test, y_test)
    print(f"Test accuracy: {accuracy}")

    # Predict probabilities and classes
    y_prob = model.predict_proba(X_train)
    y_prob = [max(row) for row in y_prob]
    y_pred = model.predict(X_train)

    # Create Series with the real, predicted classes and probabilities
    y_train = pd.Series(y_train)
    y_pred = pd.Series(y_pred)
    y_prob = pd.Series(y_prob)

    # Calculate the dark number estimates
    darker = DarkNumberCalculator()
    # Convert to binary classification 
    y_train_bin = pd.Series(y_train.apply(func=(lambda x: 1 if x == 1 else 0)))
    y_pred_bin = pd.Series(y_pred.apply(func=(lambda x: 1 if x == 1 else 0)))
    dark_number = darker.compute_dark_number(y_train_bin, y_pred_bin)
    dark_number_single_alpha = darker.compute_dark_number_single_alpha(y_train_bin, y_pred_bin, y_prob)
    dark_number_separated_alpha = darker.compute_dark_number_separated_alpha(y_train_bin, y_pred_bin, y_prob)
    dark_number_non_linear = darker.compute_dark_number_non_linear(y_train_bin, y_pred_bin, y_prob)
    dark_number_non_linear_alpha = darker.compute_dark_number_non_linear(y_train_bin, y_pred_bin, y_prob, use_alpha=True)

    # Print the results
    print(f"Dark Number (No Alpha): {dark_number}")
    print(f"Dark Number (Single Alpha Correction): {dark_number_single_alpha}")
    print(f"Dark Number (Separated Alpha Correction): {dark_number_separated_alpha}")
    print(f"Dark Number (Non-Linear Scaling): {dark_number_non_linear}")
    print(f"Dark Number (Non-Linear Scaling with Alpha correction): {dark_number_non_linear_alpha}")

    for type in ["single_alpha", "separated_alpha", "non_linear", "non_linear_alpha", "all"]:
        dark_numbers = darker.compute_dark_numbers(y_train, y_pred, y_prob, type=type, root_degree=3)
    print(dark_numbers)
    
    
if __name__ == "__main__":
    main()
