import { SigmaContainer } from "@react-sigma/core";
import { GraphLoader } from "./GraphLoader";
import { HoverCoreNode } from "./HoverCoreNode";

export function GraphCanvas() {
  return (
    <div style={{ width: "100%", height: "100%" }}>
      <SigmaContainer
        style={{ width: "100%", height: "100%" }}
        settings={{

          defaultNodeColor: "#9aa0a6",
          defaultEdgeColor: "#9aa0a6",
          labelRenderedSizeThreshold: 10,
          enableEdgeEvents: true,
          defaultDrawNodeHover: () => {},
        }}
      >
        <GraphLoader />
        <HoverCoreNode />
      </SigmaContainer>
    </div>
  );
}
