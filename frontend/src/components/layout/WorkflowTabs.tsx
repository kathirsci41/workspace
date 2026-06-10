import { NavLink } from 'react-router-dom';

const tabs = [
  ['Overview', 'overview'],
  ['Documents', 'documents'],
  ['Extraction Review', 'extraction'],
  ['Review Results', 'verification'],
  ['Open Issues', 'issues'],
  ['Export', 'exports'],
] as const;

export function WorkflowTabs({ bundleId }: { bundleId: string }) {
  return (
    <nav className="workflow-tabs" aria-label="Bundle workflow">
      {tabs.map(([label, path]) => (
        <NavLink key={label} to={`/bundles/${bundleId}/${path}`} end>
          {label}
        </NavLink>
      ))}
      <details className="workflow-tabs__more">
        <summary>More</summary>
        <div>
          <NavLink to={`/bundles/${bundleId}/audit`}>Manual Correction History</NavLink>
        </div>
      </details>
    </nav>
  );
}
