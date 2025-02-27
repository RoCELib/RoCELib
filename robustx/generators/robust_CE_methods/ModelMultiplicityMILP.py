import pandas as pd
from gurobipy import Model
from gurobipy.gurobipy import quicksum, GRB

from robustx.datasets.DatasetLoader import DatasetLoader
from robustx.lib.models.pytorch_models.SimpleNNModel import SimpleNNModel
from robustx.generators.CEGenerator import CEGenerator
from robustx.lib.tasks.ClassificationTask import ClassificationTask
from robustx.lib.intabs.WeightBiasDictionary import create_weights_and_bias_dictionary


class ModelMultiplicityMILP(CEGenerator):

    def __init__(self, dl: DatasetLoader, models: list[SimpleNNModel]):
        super().__init__(ClassificationTask(models[0], dl))
        self.gurobiModel = Model()
        self.models = models
        self.inputNodes = None
        self.outputNodes = {}

    def _generation_method(self, instance, column_name="target", neg_value=0, M=1000, epsilon=0.1, **kwargs):

        self.gurobiModel = Model()

        # Turn off the Gurobi output
        self.gurobiModel.setParam('OutputFlag', 0)

        if isinstance(instance, pd.DataFrame):
            ilist = instance.iloc[0].tolist()
        else:
            ilist = instance.tolist()

        # Dictionary to store input variables, shared across all models
        self.inputNodes = {}
        activation_states = {}
        all_nodes = {}

        # Create Gurobi variables for the inputs (shared for all models)
        for i, col in enumerate(self.task.training_data.X.columns):
            key = f"v_0_{i}"

            # Calculate the minimum and maximum values for the current column
            col_min = self.task.training_data.X[col].min()
            col_max = self.task.training_data.X[col].max()

            # Use the calculated min and max for the bounds of the variable
            self.inputNodes[key] = self.gurobiModel.addVar(lb=col_min, ub=col_max, name=key)
            all_nodes[key] = self.inputNodes[key]

        for model_idx, model in enumerate(self.models):
            weights, biases = create_weights_and_bias_dictionary(model)

            layers = [model.input_dim] + model.hidden_dim + [model.output_dim]

            # Iterate through all "hidden" layers, the first value in intabs.layers is the input layer and the
            # last value in intabs.layers is the output layer. The actual layer index whose variables we want to
            # create is layer at index layer+1
            for layer in range(len(layers) - 2):

                # Go through each layer in the layer whose variables we want to create
                for node in range(layers[layer + 1]):
                    # Create Gurobi variables for each node and their activation state
                    var_name = f"model{model_idx}_v_{layer + 1}_{node}"
                    activation_name = f"model{model_idx}_xi_{layer + 1}_{node}"

                    all_nodes[var_name] = self.gurobiModel.addVar(lb=-float('inf'), name=var_name)
                    activation_states[activation_name] = self.gurobiModel.addVar(vtype=GRB.BINARY, name=activation_name)

                    self.gurobiModel.update()

                    # 1) Add v_i_j >= 0 constraint
                    self.gurobiModel.addConstr(all_nodes[var_name] >= 0, name=f"model{model_idx}_constr1_" + var_name)

                    # 2) Add v_i_j <= M ( 1 - xi_i_j )
                    self.gurobiModel.addConstr(M * (1 - activation_states[activation_name]) >= all_nodes[var_name],
                                               name=f"model{model_idx}_constr2_" + var_name)

                    qr = quicksum((
                        weights[f'weight_l{layer}_n{prev_node_index}_to_l{layer + 1}_n{node}'] *
                        all_nodes[
                            f"model{model_idx}_v_{layer}_{prev_node_index}" if layer else f"v_0_{prev_node_index}"] for
                    prev_node_index in range(layers[layer])
                    )) + biases[f'bias_into_l{layer + 1}_n{node}']

                    # 3) Add v_i_j <= sum((W_i_j + delta)v_i-1_j + ... + M xi_i_j)
                    self.gurobiModel.addConstr(qr + M * activation_states[
                        activation_name] >= all_nodes[var_name],
                                               name=f"model{model_idx}_constr3_" + var_name)

                    self.gurobiModel.addConstr(qr <= all_nodes[var_name])

                    # sum_node = self.gurobiModel.addVar(name=f"model{model_idx}_layer{layer+1}_n{node}_sum")
                    #
                    # self.gurobiModel.addConstr(quicksum((
                    #     weights[f'weight_l{layer}_n{prev_node_index}_to_l{layer + 1}_n{node}'] *
                    #     all_nodes[
                    #         f"model{model_idx}_v_{layer}_{prev_node_index}" if layer else f"v_0_{prev_node_index}"] for prev_node_index in range(layers[layer])
                    # )) + biases[f'bias_into_l{layer + 1}_n{node}'] == sum_node)
                    #
                    # self.gurobiModel.addGenConstrMax(all_nodes[var_name], [sum_node, 0.0], name=f"model{model_idx}_l{layer+1}_n{node}_relu")

                    self.gurobiModel.update()

            outputNode = self.gurobiModel.addVar(lb=-float('inf'), vtype=GRB.CONTINUOUS,
                                                 name=f'model{model_idx}_output_node')

            self.outputNodes[f'model{model_idx}_output_node'] = outputNode

            # constraint 1: node <= ub(W)x + ub(B)
            self.gurobiModel.addConstr(quicksum((
                weights[f'weight_l{len(layers) - 2}_n{prev_node_index}_to_l{len(layers) - 1}_n0'] *
                all_nodes[
                    f"model{model_idx}_v_{len(layers) - 2}_{prev_node_index}" if len(
                        layers) - 2 else f"v_0_{prev_node_index}"] for prev_node_index in range(layers[len(layers) - 2])
            )) + biases[f'bias_into_l{len(layers) - 1}_n0'] == outputNode,
                                       name=f'model{model_idx}_output_node_C1')

            if not neg_value:
                self.gurobiModel.addConstr(outputNode - epsilon >= 0,
                                           name=f"model{model_idx}_output_node_lb_>=0")
            else:
                self.gurobiModel.addConstr(outputNode + epsilon <= 0,
                                           name=f"model{model_idx}_output_node_ub_<=0")

            self.gurobiModel.update()

        objective = self.gurobiModel.addVar(name="objective")

        self.gurobiModel.addConstr(objective == quicksum(
            (self.inputNodes[f'v_0_{i}'] - ilist[i]) ** 2 for i in range(len(self.task.training_data.X.columns))))

        self.gurobiModel.update()

        self.gurobiModel.optimize()

        status = self.gurobiModel.status

        # If no solution was obtained that means the INN could not be modelled
        if status != GRB.status.OPTIMAL:
            return pd.DataFrame()

        ce = []

        for v in self.gurobiModel.getVars():
            if 'v_0_' in v.varName:
                ce.append(v.getAttr(GRB.Attr.X))
        return pd.DataFrame(ce).T
