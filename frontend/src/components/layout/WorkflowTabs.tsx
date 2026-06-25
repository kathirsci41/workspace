import { NavLink } from 'react-router-dom';

const tabs = [
  ['Overview', 'overview'],
  ['Documents', 'documents'],
  ['Extraction Review', 'extraction'],
  ['Review Results', 'verification'],
  ['Open Issues', 'issues'],
  ['Export', 'exports'],
  ['Audit', 'audit'],
] as const;

export function WorkflowTabs({ bundleId }: { bundleId: string }) {
  return (
    <nav className="workflow-tabs" aria-label="Order workflow">
      {tabs.map(([label, path]) => (
        <NavLink key={label} to={`/bundles/${bundleId}/${path}`} end>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
