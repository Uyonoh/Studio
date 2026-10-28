export default function ProjectsPage() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#E8EAF0]">
            Projects
          </h1>
          <p className="text-sm text-[#9AA1B2] mt-1">
            Organize, generate, and orchestrate generative multi-modal assets.
          </p>
        </div>
      </div>
      <div className="rounded-2xl border border-[#262A35] bg-[#14161C] p-8 text-center">
        <p className="text-sm text-[#9AA1B2]">Select or create a project to get started.</p>
      </div>
    </div>
  );
}
