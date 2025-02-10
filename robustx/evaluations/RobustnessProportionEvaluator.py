from robustx.evaluations.CEEvaluator import CEEvaluator
from robustx.robustness_evaluations.DeltaRobustnessEvaluator import DeltaRobustnessEvaluator
from robustx.robustness_evaluations.ModelChangesRobustnessEvaluator import ModelChangesRobustnessEvaluator


class RobustnessProportionEvaluator(CEEvaluator):
    """
     An Evaluator class which evaluates the proportion of counterfactuals which are robust

        ...

    Attributes / Properties
    -------

    task: Task
        Stores the Task for which we are evaluating the robustness of CEs

    robustness_evaluator: ModelChangesRobustnessEvaluator
        An instance of ModelChangesRobustnessEvaluator to evaluate the robustness of the CEs

    valid_val: int
        Stores what the target value of a valid counterfactual is defined as

    target_col: str
        Stores what the target column name is

    -------

    Methods
    -------

    evaluate() -> int:
        Returns the proportion of CEs which are robust for the given parameters

    -------
    """

    def evaluate(self, counterfactuals, delta=0.005, bias_delta=0.005, M=1000000, epsilon=0.001, valid_val=1, column_name="target",
                 robustness_evaluator: ModelChangesRobustnessEvaluator.__class__ = DeltaRobustnessEvaluator,
                 **kwargs):
        """
        Evaluate the proportion of CEs which are robust for the given parameters
        @param counterfactuals: pd.DataFrame, the CEs to evaluate
        @param delta: int, delta needed for robustness evaluator
        @param bias_delta: int, bias delta needed for robustness evaluator
        @param M: int, large M needed for robustness evaluator
        @param epsilon: int, small epsilon needed for robustness evaluator
        @param column_name: str, what the target column name is
        @param valid_val: int, what the target value of a valid counterfactual is defined as
        @param robustness_evaluator: ModelChangesRobustnessEvaluator.__class__, the CLASS of the evaluator to use
        @return: Proportion of CEs which are robust
        """
        robust = 0
        cnt = 0

        # Get only the feature variables from the CEs
        instances = counterfactuals.drop(columns=[column_name, "loss"], errors='ignore')

        robustness_evaluator = robustness_evaluator(self.task)

        for _, instance in instances.iterrows():

            # Increment robust if CE is robust under given parameters
            if instance is not None and robustness_evaluator.evaluate(instance, desired_output=valid_val,
                                                                      delta=delta, bias_delta=bias_delta,
                                                                      M=M, epsilon=epsilon):
                robust += 1

            # Increment total number of CEs encountered
            cnt += 1

        return robust / cnt
