export function LoadingProjectsState() {
  return (
    <div
      data-testid="loading-projects-state"
      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
    >
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div
          key={i}
          className="bg-[#14161C] border border-[#262A35] rounded-2xl overflow-hidden shadow-card animate-pulse flex flex-col justify-between"
        >
          <div className="aspect-[16/9] bg-[#1B1E26]" />
          <div className="p-4 space-y-3">
            <div className="h-4 bg-[#1B1E26] rounded w-2/3" />
            <div className="space-y-1.5">
              <div className="h-3 bg-[#1B1E26]/60 rounded w-full" />
              <div className="h-3 bg-[#1B1E26]/60 rounded w-4/5" />
            </div>
            <div className="pt-3 border-t border-[#262A35]/50 flex justify-between">
              <div className="h-3 bg-[#1B1E26]/40 rounded w-1/3" />
              <div className="h-3 bg-[#1B1E26]/40 rounded w-12" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
