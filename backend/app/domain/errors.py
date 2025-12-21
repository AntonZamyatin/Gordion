class GraphError(Exception):
    pass

class NodeExists(GraphError):
    pass

class NodeNotFound(GraphError):
    pass

class EdgeExists(GraphError):
    pass

class EdgeNotFound(GraphError):
    pass

class InvalidEdgeEndpoint(GraphError):
    pass
