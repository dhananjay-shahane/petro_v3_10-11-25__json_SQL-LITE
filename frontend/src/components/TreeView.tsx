import { ChevronRight, ChevronDown, Folder, File } from "lucide-react";
import { useState } from "react";

interface TreeNode {
  id: string;
  label: string;
  type: "folder" | "file";
  children?: TreeNode[];
}

interface TreeViewProps {
  data: TreeNode[];
  level?: number;
}

function TreeItem({ node, level = 0 }: { node: TreeNode; level?: number }) {
  const [isExpanded, setIsExpanded] = useState(level === 0);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center h-7 px-2 cursor-pointer hover-elevate"
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => hasChildren && setIsExpanded(!isExpanded)}
        data-testid={`tree-item-${node.id}`}
      >
        {hasChildren ? (
          isExpanded ? (
            <ChevronDown className="w-4 h-4 mr-1 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-4 h-4 mr-1 text-muted-foreground" />
          )
        ) : (
          <span className="w-4 mr-1" />
        )}
        {node.type === "folder" ? (
          <Folder className="w-4 h-4 mr-2 text-primary" />
        ) : (
          <File className="w-4 h-4 mr-2 text-muted-foreground" />
        )}
        <span className="text-sm text-foreground truncate">{node.label}</span>
      </div>
      {hasChildren && isExpanded && (
        <div>
          {node.children?.map((child) => (
            <TreeItem key={child.id} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TreeView({ data, level = 0 }: TreeViewProps) {
  return (
    <div className="py-2">
      {data.map((node) => (
        <TreeItem key={node.id} node={node} level={level} />
      ))}
    </div>
  );
}
