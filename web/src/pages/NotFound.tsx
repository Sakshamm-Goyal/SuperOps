import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { Button, Empty } from "../components/ui";

export default function NotFound() {
  return (
    <Empty icon={Compass} title="No page here" action={<Link to="/app"><Button>Back to overview</Button></Link>}>
      The address doesn't match a workbench page. Records are scoped to your tenant, so a foreign or unknown ID also lands here.
    </Empty>
  );
}
