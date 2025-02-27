import pandas as pd
from gurobipy import Model, GRB
from gurobipy.gurobipy import quicksum, abs_
from robustx.lib.OptSolver import OptSolver
from robustx.generators.CEGenerator import CEGenerator
from robustx.lib.tasks.Task import Task


class MCE(CEGenerator):
    """
    A counterfactual explanation generator that uses Mixed-Integer Linear Programming (MILP) to find counterfactual explanations.

    Inherits from the CEGenerator class and implements the _generation_method to find
    counterfactual explanations using MILP with the Gurobi optimizer.

    Attributes:
        _task (Task): The task to solve, inherited from CEGenerator.
        __customFunc (callable, optional): A custom distance function, inherited from CEGenerator.
        opt (OptSolver): An optimizer instance for setting up and solving the MILP problem.
    """

    def __init__(self, ct: Task):
        """
        Initializes the MCE recourse generator with a given task.

        @param ct: The task to solve, provided as a Task instance.
        """
        super().__init__(ct)
        self.opt = OptSolver(ct)

    def _generation_method(self, instance, column_name="target", neg_value=0, M=10000, epsilon=0.0001,
                           minimum_distance=0.0, **kwargs) -> pd.DataFrame:
        """
        Generates a counterfactual explanation for a provided instance using MILP.

        @param instance: The instance for which to generate a counterfactual. Can be a DataFrame or Series.
        @param column_name: The name of the target column. (Not used in this method)
        @param neg_value: The value considered negative in the target variable.
        @param M: A large constant used for modeling constraints.
        @param epsilon: A small constant used for modeling constraints.
        @param minimum_distance: The minimum distance constraint for the output node.
        @param kwargs: Additional keyword arguments.
        @return: A DataFrame containing the counterfactual explanation for the provided instance.
        """

        # Convert instance to list
        if isinstance(instance, pd.DataFrame):
            ilist = instance.iloc[0].tolist()
        else:
            ilist = instance.tolist()

        # Reset model of OptSolver
        self.opt.gurobiModel = Model()

        # Set up without fixed inputs
        self.opt.setup(instance=instance, delta=0, M=M, fix_inputs=False)

        # Add final constrain after set up
        if not neg_value:
            self.opt.gurobiModel.addConstr(self.opt.outputNode - epsilon >= minimum_distance, name="output_node_lb_>=0")
        else:
            self.opt.gurobiModel.addConstr(self.opt.outputNode + epsilon <= minimum_distance, name="output_node_ub_<=0")

        # Set minimising objective
        # objective = self.opt.gurobiModel.addVar(name="objective")
        # self.opt.gurobiModel.addConstr(objective == quicksum(
        #     (self.opt.inputNodes[f'v_0_{i}'] - ilist[i]) ** 2 for i in range(len(self.task.training_data.X.columns))))

        # Set minimising objective with L1
        obj_vars_l1 = []
        for i in range(len(self.task.training_data.X.columns)):
            self.opt.gurobiModel.update()
            key = f"v_0_{i}"
            this_obj_var_l1 = self.opt.gurobiModel.addVar(vtype=GRB.SEMICONT, lb=-GRB.INFINITY, name=f"objl1_feat_{i}")
            self.opt.gurobiModel.addConstr(this_obj_var_l1 >= ilist[i] - self.opt.inputNodes[key])
            self.opt.gurobiModel.addConstr(this_obj_var_l1 >= self.opt.inputNodes[key] - ilist[i])
            obj_vars_l1.append(this_obj_var_l1)
        self.opt.gurobiModel.setObjective(quicksum(obj_vars_l1), GRB.MINIMIZE)
        self.opt.gurobiModel.Params.NonConvex = 2
        self.opt.gurobiModel.update()
        self.opt.gurobiModel.optimize()

        status = self.opt.gurobiModel.status

        # If no solution was obtained that means the INN could not be modelled
        if status != GRB.status.OPTIMAL:
            print("No solution found using MCE!")
            return pd.DataFrame(instance).T

        ce = []

        # Find input variables and final CE
        for v in self.opt.gurobiModel.getVars():
            if 'v_0_' in v.varName:
                ce.append(v.getAttr(GRB.Attr.X))

        res = pd.DataFrame(ce).T
        res.columns = instance.index
        return res
